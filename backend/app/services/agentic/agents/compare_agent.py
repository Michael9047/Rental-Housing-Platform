"""对比 Agent —— 多维度房源对比（评分+LLM解释+7维分析，独立无 AgentService 依赖）

Phase 3: 从 AgentService 迁移全部对比逻辑。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.models.poi import PropertyPOI
from app.models.review import Review, ReviewStatus
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult, AgentError, AgentErrorType
from app.services.agentic.shared import (
    build_dimension_analysis,
    property_to_dict,
)
from app.services.compare_scoring import (
    DIMENSION_LABELS,
    PRIORITY_LABELS,
    PropertyMetrics,
    compute_scores,
    format_commute,
    nearest_transit_meters,
    normalize_priority,
)

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_HINT = "（AI 分析暂不可用，已按筛选条件为您检索）"

COMPARE_SYSTEM_PROMPT = """你是面向留学生的海外租房对比助手。系统已计算好每套房的综合得分和分项得分。你的任务是解释分析，不是打分。

══════════════════════════════
示例（Few-Shot）
══════════════════════════════
对比：公寓A(¥1800) vs 公寓B(¥1500) vs 公寓C(¥1950)，用户通勤优先

→ summary: 「如果通勤是你的第一优先级，公寓A完胜——步行10分钟到校，多睡20分钟。公寓B胜在便宜+配套，公寓C安静但通勤偏慢。」

→ 对每套：公寓A pros=["步行10分钟到校","独卫精装"] cons=["价格偏高¥1800"]；公寓B pros=["价格最低¥1500","楼下商业街"] cons=["合租无独卫","面积偏小"]；公寓C pros=["安静适合学习","采光好"] cons=["公交15分钟","价格最贵¥1950"]

→ recommendation: 「综合通勤+性价比，公寓A最值。每天多出20分钟+独卫+精装，每月只多300块，值。」

══════════════════════════════
规则
══════════════════════════════
1. 基于给出的真实字段，禁止编造。
2. 每套房源都要覆盖。
3. score 原样使用系统计算的得分，禁止修改。
4. pros/cons 结合价格、通勤、面积、设施来写。
5. recommendation 呼应用户优先级（通勤优先/预算优先/均衡）。
6. 口语化，像朋友在给建议，用「你」不是「您」。

只输出 JSON，格式：
{
  "summary": "综合对比结论，一两句话",
  "items": [
    {
      "property_id": 1,
      "pros": ["价格最低", "步行3分钟到地铁"],
      "cons": ["面积较小"],
      "score": 86,
      "best_for": "预算有限、单人居住"
    }
  ],
  "recommendation": "按您的优先级推荐房源 1，因为..."
}"""


class CompareAgent(BaseAgent):
    """多维度房源对比 Agent。

    职责：对比一组房源（价格/通勤/空间/评价），生成 LLM 解释 + 7 维 Markdown 分析。
    替代 AgentService 中的 compare_cart / _compare_props / _gather_compare_metrics / _rule_based_compare。
    """

    name = "compare_agent"
    description = "多维度房源对比（价格/通勤/空间/评价）。独立于 AgentService。"
    tools = ["compare_dimensions", "cart_view", "poi_lookup", "commute_calc"]

    def __init__(self, session: AsyncSession | None = None, tool_registry=None) -> None:
        super().__init__(tool_registry)
        self._session = session

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("CompareAgent 未绑定 DB session")
        return self._session

    # ── 核心对比入口 ──────────────────────────────────────────────

    async def compare(
        self,
        user_id: int,
        property_ids: list[int] | None = None,
        priority: str | None = None,
        cart_agent: CartService | None = None
    ) -> dict[str, Any]:
        """对比房源。

        - 传入 property_ids：只对比这些房源。
        - 未传：对比整个购物车（需要 cart_agent）。
        - priority：用户优先级（balanced/budget/commute/space）。
        """
        if property_ids:
            props: list[Property] = []
            for pid in dict.fromkeys(property_ids):
                prop = await self.session.get(Property, pid)
                if prop is not None:
                    props.append(prop)
            if len(props) < 2:
                raise ValueError("请至少选择 2 套有效房源进行对比")
            return await self._compare_props(props, priority)

        # 从购物车取
        if cart_agent is None:
            raise ValueError("购物车对比需要提供 cart_agent")
        _cart, items = await cart_agent.get_cart_items(user_id)
        if not items:
            raise ValueError("购物车为空，请先添加房源再对比")

        props = []
        for item in items:
            prop = await self.session.get(Property, item.property_id)
            if prop is not None:
                props.append(prop)
        if not props:
            raise ValueError("购物车中的房源已不存在")

        return await self._compare_props(props, priority)

    # ── 指标聚合 ──────────────────────────────────────────────────

    async def _gather_compare_metrics(
        self, props: list[Property]
    ) -> tuple[list[PropertyMetrics], dict[int, dict]]:
        """为对比补充真实数据：POI 通勤距离 + 机构评价聚合。"""
        ids = [p.id for p in props]

        pois: dict[int, PropertyPOI] = {}
        try:
            rows = await self.session.scalars(
                select(PropertyPOI).where(PropertyPOI.property_id.in_(ids))
            )
            pois = {poi.property_id: poi for poi in rows}
        except Exception:
            logger.exception("加载 POI 数据失败，通勤维度取中性分")

        rating_by_inst: dict[int, tuple[float, int]] = {}
        inst_ids = {p.institute_id for p in props if p.institute_id}
        if inst_ids:
            try:
                rows = await self.session.execute(
                    select(
                        Review.institute_id,
                        func.avg(Review.rating),
                        func.count(Review.id),
                    )
                    .where(
                        Review.institute_id.in_(inst_ids),
                        Review.status == ReviewStatus.approved,
                    )
                    .group_by(Review.institute_id)
                )
                rating_by_inst = {r[0]: (float(r[1]), int(r[2])) for r in rows}
            except Exception:
                logger.exception("加载评价聚合失败，评分维度取中性分")

        metrics: list[PropertyMetrics] = []
        extras: dict[int, dict] = {}
        for p in props:
            poi = pois.get(p.id)
            transit = nearest_transit_meters(poi.poi_data if poi else None)
            rating, count = (None, 0)
            if p.institute_id and p.institute_id in rating_by_inst:
                rating, count = rating_by_inst[p.institute_id]
            metrics.append(
                PropertyMetrics(
                    property_id=p.id,
                    price=float(p.price_monthly),
                    area=float(p.area_sqm) if p.area_sqm else None,
                    transit_meters=transit,
                    rating=rating,
                    review_count=count,
                )
            )
            extras[p.id] = {
                "commute": format_commute(transit),
                "rating": round(rating, 1) if rating is not None else None,
                "review_count": count,
            }
        return metrics, extras

    # ── 对比核心（评分 + LLM 解释） ──────────────────────────────

    async def _compare_props(
        self, props: list[Property], priority: str | None = None
    ) -> dict[str, Any]:
        """评分与解释分离：确定性评分 + LLM 解释（不可用时降级为规则）。"""
        by_id = {p.id: p for p in props}
        pr = normalize_priority(priority)
        metrics, extras = await self._gather_compare_metrics(props)
        scores = compute_scores(metrics, pr)

        def _base_item(pid: int) -> dict[str, Any]:
            return {
                "property_id": pid,
                "title": by_id[pid].title,
                "score": scores[pid]["total"],
                "score_breakdown": scores[pid]["breakdown"],
                "commute": extras[pid]["commute"],
                "rating": extras[pid]["rating"],
                "review_count": extras[pid]["review_count"],
                "property": by_id[pid],
            }

        if self.llm_service.is_available:
            try:
                lines = []
                for i, p in enumerate(props, 1):
                    d = property_to_dict(p)
                    e = extras[p.id]
                    s = scores[p.id]
                    lines.append(
                        f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | "
                        f"月租: ¥{d['price_monthly']} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
                        f"面积: {d['area_sqm'] or '未知'}㎡ | 通勤: {e['commute'] or '无数据'} | "
                        f"评价: {(str(e['rating']) + '分/' + str(e['review_count']) + '条') if e['rating'] is not None else '暂无'} | "
                        f"简介: {d['description'] or '无'}\n"
                        f"   系统得分（禁止修改）: 综合 {s['total']} | "
                        + " ".join(f"{DIMENSION_LABELS[k]} {v}" for k, v in s["breakdown"].items())
                    )
                user_prompt = (
                    f"用户优先级：{PRIORITY_LABELS[pr]}\n\n"
                    f"待对比房源（数据库真实数据 + 系统计算得分）：\n" + "\n".join(lines)
                )
                result = await self.llm_service.complete_json(
                    COMPARE_SYSTEM_PROMPT, user_prompt, max_tokens=2000
                )

                parsed: dict[int, dict] = {}
                for it in result.get("items", []):
                    pid = it.get("property_id")
                    if pid in by_id:
                        parsed[pid] = it

                items_out = []
                for p in props:
                    item = _base_item(p.id)
                    it = parsed.get(p.id, {})
                    item["pros"] = [str(x) for x in it.get("pros", [])] or ["条件均衡"]
                    item["cons"] = [str(x) for x in it.get("cons", [])]
                    item["best_for"] = str(it.get("best_for", ""))
                    items_out.append(item)

                if parsed:
                    dim_analysis = build_dimension_analysis(props, scores, extras, pr, result)
                    return {
                        "summary": str(result.get("summary", "")),
                        "dimension_analysis": dim_analysis,
                        "items": items_out,
                        "recommendation": str(result.get("recommendation", "")),
                        "ai_available": True,
                        "priority": pr,
                    }
            except Exception:
                logger.exception("LLM 对比解释生成失败，降级为规则解释（得分不变）")

        return self._rule_based_compare(props, scores, extras, pr)

    # ── 规则降级 ──────────────────────────────────────────────────

    def _rule_based_compare(
        self,
        props: list[Property],
        scores: dict[int, dict],
        extras: dict[int, dict],
        priority: str,
    ) -> dict[str, Any]:
        """LLM 不可用时的规则解释。"""
        by_id = {p.id: p for p in props}

        best: dict[str, int] = {}
        for dim in DIMENSION_LABELS:
            best[dim] = max(scores[p.id]["breakdown"][dim] for p in props)

        dim_pros = {
            "price": "价格最有优势",
            "commute": "通勤最便利",
            "space": "空间最宽敞",
            "rating": "评价最好",
        }

        items_out = []
        for p in props:
            b = scores[p.id]["breakdown"]
            pros = [
                text for dim, text in dim_pros.items()
                if b[dim] == best[dim] and b[dim] > 60 and len(props) > 1
            ]
            cons = []
            if b["price"] <= 45:
                cons.append("价格偏高")
            if b["space"] <= 45:
                cons.append("面积偏小")
            if extras[p.id]["commute"] is None:
                cons.append("暂无通勤数据")
            if not pros:
                pros.append("条件均衡")

            top_dim = max(b, key=lambda k: b[k])
            items_out.append({
                "property_id": p.id,
                "title": p.title,
                "pros": pros,
                "cons": cons,
                "score": scores[p.id]["total"],
                "score_breakdown": b,
                "best_for": f"{DIMENSION_LABELS[top_dim]}优先",
                "commute": extras[p.id]["commute"],
                "rating": extras[p.id]["rating"],
                "review_count": extras[p.id]["review_count"],
                "property": by_id[p.id],
            })

        prices = [float(p.price_monthly) for p in props]
        winner = max(props, key=lambda p: scores[p.id]["total"])
        fake_result = {
            "summary": f"按「{PRIORITY_LABELS[priority]}」共对比 {len(props)} 套房源，价格区间 ¥{min(prices):.0f} - ¥{max(prices):.0f}。{AI_UNAVAILABLE_HINT}",
            "recommendation": f"按「{PRIORITY_LABELS[priority]}」综合得分最高的是「{winner.title}」（{scores[winner.id]['total']} 分）。",
        }

        return {
            "summary": fake_result["summary"],
            "dimension_analysis": build_dimension_analysis(props, scores, extras, priority, fake_result),
            "items": items_out,
            "recommendation": fake_result["recommendation"],
            "ai_available": False,
            "priority": priority,
        }

    # ── Agent 接口（供 Supervisor 调用） ──────────────────────────

    async def handle(self, context: AgentContext) -> AgentResult:
        """对比入口：从 AgentContext 提取 user_id 和 property_ids，执行对比。"""
        try:
            cart_agent = CartService(session=self.session)
            result = await self.compare(
                user_id=context.user_id or 0,
                property_ids=context.extra.get("compare_property_ids") if context.extra else None,
                cart_agent=cart_agent,
            )
            return AgentResult(
                content=result.get("summary", ""),
                success=True,
                data=result,
            )
        except ValueError as exc:
            return AgentResult(content=str(exc), success=True, data={"error": str(exc)})
        except Exception as exc:
            return AgentResult(
                content="",
                success=False,
                error=AgentError(
                    type_=AgentErrorType.TOOL_FAILURE,
                    message=str(exc),
                    agent_id="compare_agent",
                ),
            )

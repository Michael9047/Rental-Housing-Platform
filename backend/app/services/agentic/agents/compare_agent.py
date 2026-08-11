"""对比 Agent —— 多维度房源对比（评分+LLM解释+7维分析，独立无 AgentService 依赖）

Phase 3: 从 AgentService 迁移全部对比逻辑。
"""
from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.poi import InstitutePOI
from app.models.review import Review, ReviewStatus
from app.models.unit_type import UnitType
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.agents.cart_agent import CartService
from app.services.agentic.orchestration.types import AgentContext, AgentResult, AgentError, AgentErrorType
from app.services.agentic.shared import (
    format_unit_type_money,
    guard_price_item_narratives,
    guard_price_narrative,
    property_to_dict,
    unit_type_title,
)
from app.services.compare_scoring import (
    DIMENSION_LABELS,
    PRIORITY_LABELS,
    PropertyMetrics,
    compute_scores,
    currencies_are_comparable,
    format_commute,
    nearest_transit_meters,
    normalize_priority,
)

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_HINT = "（AI 总结暂不可用，已保留确定性对比结果。）"

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
7. 只有所有候选的币种都非空且完全一致时才能比较价格。币种缺失或不同时不得声称最低、更便宜或最划算。
8. summary 和 recommendation 不得引用或展示综合分、分项分、得分或评分；score 仅供系统内部结构化处理。

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

COMPARE_STREAM_SYSTEM_PROMPT = """你是留学生租房对比助手。仅依据用户提供的真实字段，用简洁中文比较候选并呼应用户优先级；不得编造，不得重算、引用或展示综合分、分项分、得分或评分。仅输出80—160字：先给结论，再说最关键的1—2项取舍，最后给建议；不要复述所有维度。币种缺失或不一致时禁止比较租金高低。不要输出JSON、Markdown、标题或表格。"""

_PUBLIC_SCORE_PATTERN = re.compile(
    r"(?:综合|分项|价格|通勤|空间|安全)?(?:得分|评分)|中性分|\d+(?:\.\d+)?\s*分"
)
_STREAM_INTERRUPTED_HINT = "\n\n（AI 对比总结生成中断，请结合上方结构化信息选择。）"


class CompareAgent(BaseAgent):
    """多维度房源对比 Agent。

    职责：对比一组户型（价格/通勤/空间/评价/安全），生成 LLM 解释与确定性分析。
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
        cart_agent: CartService | None = None,
        token_sink: Callable[[str], Awaitable[None]] | None = None,
        status_sink: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """对比房源。

        - 传入 property_ids：按 UnitType.id 对比这些户型（兼容字段名）。
        - 未传：对比整个购物车（需要 cart_agent）。
        - priority：用户优先级（balanced/budget/commute/space/safety）。
        """
        if property_ids is not None:
            unique_ids = list(dict.fromkeys(property_ids))
            if not 2 <= len(unique_ids) <= 5:
                raise ValueError("请选择 2-5 个户型进行对比")
            rows = await self.session.scalars(
                select(UnitType)
                .options(selectinload(UnitType.institute))
                .where(
                    UnitType.id.in_(unique_ids),
                    UnitType.deleted_at.is_(None),
                )
            )
            by_id = {unit_type.id: unit_type for unit_type in rows}
            props = [by_id[unit_type_id] for unit_type_id in unique_ids if unit_type_id in by_id]
            if len(props) != len(unique_ids):
                raise ValueError("部分户型不存在或已删除")
            return await self._compare_props(
                props,
                priority,
                token_sink=token_sink,
                status_sink=status_sink,
            )

        # 从购物车取
        if cart_agent is None:
            raise ValueError("购物车对比需要提供 cart_agent")
        _cart, items = await cart_agent.get_cart_items(user_id)
        if not 2 <= len(items) <= 5:
            raise ValueError("候选清单中请选择 2-5 个户型进行对比")

        props = [item.unit_type for item in items if item.unit_type is not None]
        if len(props) != len(items):
            raise ValueError("候选清单中的部分户型已不存在")

        return await self._compare_props(
            props,
            priority,
            token_sink=token_sink,
            status_sink=status_sink,
        )

    # ── 指标聚合 ──────────────────────────────────────────────────

    async def _gather_compare_metrics(
        self, props: list[UnitType]
    ) -> tuple[list[PropertyMetrics], dict[int, dict]]:
        """为对比补充真实数据：POI 通勤距离 + 机构评价聚合。"""
        pois: dict[int, InstitutePOI] = {}
        try:
            rows = await self.session.scalars(
                select(InstitutePOI).where(
                    InstitutePOI.institute_id.in_({p.institute_id for p in props})
                )
            )
            pois = {poi.institute_id: poi for poi in rows}
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
            poi = pois.get(p.institute_id)
            transit = nearest_transit_meters(poi.poi_data if poi else None)
            safety_score = None
            if poi and isinstance(poi.safety_data, dict):
                raw_safety = poi.safety_data.get("safety_score")
                if isinstance(raw_safety, (int, float)):
                    safety_score = float(raw_safety)
            rating, count = (None, 0)
            if p.institute_id and p.institute_id in rating_by_inst:
                rating, count = rating_by_inst[p.institute_id]
            metrics.append(
                PropertyMetrics(
                    property_id=p.id,
                    price=float(p.base_rent),
                    area=float(p.area_sqm) if p.area_sqm else None,
                    transit_meters=transit,
                    rating=rating,
                    review_count=count,
                    safety_score=safety_score,
                    currency=p.currency,
                )
            )
            extras[p.id] = {
                "commute": format_commute(transit),
                "rating": round(rating, 1) if rating is not None else None,
                "review_count": count,
                "safety_score": safety_score,
            }
        return metrics, extras

    # ── 对比核心（评分 + LLM 解释） ──────────────────────────────

    async def _compare_props(
        self,
        props: list[UnitType],
        priority: str | None = None,
        token_sink: Callable[[str], Awaitable[None]] | None = None,
        status_sink: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """评分与解释分离：确定性评分 + LLM 解释（不可用时降级为规则）。"""
        by_id = {p.id: p for p in props}
        pr = normalize_priority(priority)
        metrics, extras = await self._gather_compare_metrics(props)
        scores = compute_scores(metrics, pr)
        candidate_currencies = [metric.currency for metric in metrics]
        if status_sink is not None:
            await status_sink("generating", "正在生成对比解读")

        def _base_item(pid: int) -> dict[str, Any]:
            return {
                "property_id": pid,
                "title": unit_type_title(by_id[pid]),
                "score": scores[pid]["total"],
                "score_breakdown": scores[pid]["breakdown"],
                "commute": extras[pid]["commute"],
                "rating": extras[pid]["rating"],
                "review_count": extras[pid]["review_count"],
                "safety_score": extras[pid]["safety_score"],
                "property": by_id[pid],
            }

        def _comparison_user_prompt() -> str:
            lines = []
            for i, p in enumerate(props, 1):
                d = property_to_dict(p)
                e = extras[p.id]
                lines.append(
                    f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | "
                    f"月租: {format_unit_type_money(p, d['price_monthly'])} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
                    f"面积: {d['area_sqm'] or '未知'}㎡ | 通勤: {e['commute'] or '无数据'} | "
                    f"评价记录: {('已审核' + str(e['review_count']) + '条') if e['rating'] is not None else '暂无'} | "
                    f"安全数据: {'已登记' if e['safety_score'] is not None else '暂无'} | "
                    f"简介: {d['description'] or '无'}"
                )
            return (
                f"用户优先级：{PRIORITY_LABELS[pr]}\n\n"
                "待对比户型（数据库真实数据）：\n" + "\n".join(lines)
            )

        # Agent SSE 使用纯文本解读 prompt，直接转发模型原始 token；结构化
        # items 继续采用确定性规则，避免为了流式展示而增量解析 JSON。
        if (
            token_sink is not None
            and self.llm_service.is_available
        ):
            streamed_parts: list[str] = []
            fallback = self._rule_based_compare(props, scores, extras, pr)
            try:
                async for token in self.llm_service.complete_text_stream(
                    messages=[
                        {"role": "system", "content": COMPARE_STREAM_SYSTEM_PROMPT},
                        {"role": "user", "content": _comparison_user_prompt()},
                    ],
                    temperature=0.1,
                    max_tokens=260,
                ):
                    if not token:
                        continue
                    streamed_parts.append(token)
                    await token_sink(token)
                narrative = "".join(streamed_parts)
                if not narrative.strip():
                    raise ValueError("LLM 返回空回复")
                return {
                    "summary": narrative.strip(),
                    "dimension_analysis": narrative,
                    "items": fallback["items"],
                    "recommendation": fallback["recommendation"],
                    "ai_available": True,
                    "priority": pr,
                    "_reply_streamed": True,
                }
            except Exception:
                logger.exception("LLM 对比流式解读失败")
                if streamed_parts:
                    await token_sink(_STREAM_INTERRUPTED_HINT)
                    return {
                        "summary": "".join(streamed_parts).strip(),
                        "dimension_analysis": "".join(streamed_parts) + _STREAM_INTERRUPTED_HINT,
                        "items": fallback["items"],
                        "recommendation": fallback["recommendation"],
                        "ai_available": False,
                        "priority": pr,
                        "_reply_streamed": True,
                    }
                return fallback

        if self.llm_service.is_available:
            try:
                result = await self.llm_service.complete_json(
                    COMPARE_SYSTEM_PROMPT, _comparison_user_prompt(), max_tokens=2000
                )
                safe_summary, safe_recommendation = guard_price_narrative(
                    str(result.get("summary", "")),
                    str(result.get("recommendation", "")),
                    candidate_currencies,
                )
                fallback_summary, fallback_recommendation, fallback_narrative = (
                    self._build_concise_public_summary(props, scores, pr)
                )
                if not currencies_are_comparable(candidate_currencies):
                    safe_summary = "候选币种缺失或不一致，当前只并列展示原始月租，不直接判断高低。"
                    safe_recommendation = "建议先确认币种和统一换算口径，再结合其他真实差异选择。"
                if not safe_summary.strip() or _PUBLIC_SCORE_PATTERN.search(safe_summary):
                    safe_summary = fallback_summary
                if (
                    not safe_recommendation.strip()
                    or _PUBLIC_SCORE_PATTERN.search(safe_recommendation)
                ):
                    safe_recommendation = fallback_recommendation
                result = {
                    **result,
                    "summary": safe_summary,
                    "recommendation": safe_recommendation,
                }

                parsed: dict[int, dict] = {}
                for it in result.get("items", []):
                    pid = it.get("property_id")
                    if pid in by_id:
                        parsed[pid] = it

                items_out = []
                for p in props:
                    item = _base_item(p.id)
                    it = parsed.get(p.id, {})
                    pros, cons = guard_price_item_narratives(
                        [str(x) for x in it.get("pros", [])],
                        [str(x) for x in it.get("cons", [])],
                        candidate_currencies,
                    )
                    item["pros"] = pros or ["条件均衡"]
                    item["cons"] = cons
                    item["best_for"] = str(it.get("best_for", ""))
                    items_out.append(item)

                if parsed:
                    public_parts = [safe_summary.strip(), safe_recommendation.strip()]
                    dim_analysis = " ".join(part for part in public_parts if part)
                    if not dim_analysis:
                        dim_analysis = fallback_narrative
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

    @staticmethod
    def _build_concise_public_summary(
        props: list[UnitType],
        scores: dict[int, dict],
        priority: str,
        *,
        ai_unavailable: bool = False,
    ) -> tuple[str, str, str]:
        """用内部排序生成不暴露数值的短总结。"""
        winner = max(props, key=lambda prop: scores[prop.id]["total"])
        winner_breakdown = scores[winner.id]["breakdown"]
        other_breakdowns = [
            scores[prop.id]["breakdown"] for prop in props if prop.id != winner.id
        ]
        public_labels = {
            "price": "租金",
            "commute": "通勤",
            "space": "空间",
            "rating": "住客反馈",
            "safety": "安全数据",
        }
        advantages = [
            public_labels[dimension]
            for dimension, value in winner_breakdown.items()
            if dimension in public_labels
            and other_breakdowns
            and value > max(other.get(dimension, value) for other in other_breakdowns)
        ][:2]
        conclusion = (
            f"综合来看，在「{PRIORITY_LABELS[priority]}」下，"
            f"「{unit_type_title(winner)}」更适合作为首选。"
        )
        tradeoff = (
            f"它的主要优势在{'和'.join(advantages)}，其他候选仍有各自取舍。"
            if advantages
            else "候选整体接近，关键取舍仍取决于你最看重的实际条件。"
        )
        recommendation = "建议结合上方真实字段确认首要条件后再做最终选择。"
        summary = conclusion + tradeoff
        narrative = summary + recommendation
        if ai_unavailable:
            narrative += AI_UNAVAILABLE_HINT
        return summary, recommendation, narrative

    def _rule_based_compare(
        self,
        props: list[UnitType],
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
            "safety": "周边安全评分最高",
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
                "title": unit_type_title(p),
                "pros": pros,
                "cons": cons,
                "score": scores[p.id]["total"],
                "score_breakdown": b,
                "best_for": f"{DIMENSION_LABELS[top_dim]}优先",
                "commute": extras[p.id]["commute"],
                "rating": extras[p.id]["rating"],
                "review_count": extras[p.id]["review_count"],
                "safety_score": extras[p.id]["safety_score"],
                "property": by_id[p.id],
            })

        summary, recommendation, narrative = self._build_concise_public_summary(
            props,
            scores,
            priority,
            ai_unavailable=True,
        )

        return {
            "summary": summary,
            "dimension_analysis": narrative,
            "items": items_out,
            "recommendation": recommendation,
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

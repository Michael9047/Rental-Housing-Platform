"""对比 Agent —— 多维度房源对比（评分+LLM解释+7维分析，独立无 AgentService 依赖）

Phase 3: 从 AgentService 迁移全部对比逻辑。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models.property import Property
from app.models.poi import PropertyPOI
from app.models.review import Review, ReviewStatus
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult, AgentError, AgentErrorType
from app.services.agentic.shared import (
    build_dimension_analysis,
    comparable_price_cny,
    format_property_money,
    property_currency,
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

COMPARE_STREAM_SYSTEM_PROMPT = """你是面向留学生的租房对比顾问。根据系统提供的真实房源字段和确定性得分，直接输出简洁自然的中文对比说明。

规则：
1. 先给结论，再按价格、通勤、空间和评价解释关键差异。
2. 必须覆盖每套房，并呼应用户的优先级。
3. 得分和房源字段原样使用，禁止编造设施、通勤、政策或费用。
4. 缺失数据要明确说「暂无数据」。
5. 不要输出 JSON，不要重新计算得分，总长度控制在 500 字内。"""


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

    async def _load_properties(self, property_ids: list[int]) -> list[Property]:
        """按传入顺序读取房源；旧库缺失三层表时使用扁平房源事实。"""
        ordered_ids = list(dict.fromkeys(property_ids))
        if not ordered_ids:
            return []
        from app.services.property_service import PropertyService

        property_service = PropertyService(self.session)
        connection = await self.session.connection()
        existing_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns(
                    Property.__tablename__
                )
            }
        )
        rows = list(await self.session.scalars(
            select(Property)
            .where(Property.id.in_(ordered_ids))
            .options(*property_service._legacy_read_options(
                existing_columns=existing_columns
            ))
        ))
        rows = [property_service._apply_legacy_defaults(prop) for prop in rows]
        by_id = {prop.id: prop for prop in rows}
        return [by_id[property_id] for property_id in ordered_ids if property_id in by_id]

    async def _resolve_compare_properties(
        self,
        user_id: int,
        property_ids: list[int] | None,
        cart_agent: CartService | None,
    ) -> list[Property]:
        """按显式 ID 或候选清单解析待对比房源。"""
        if property_ids:
            props = await self._load_properties(property_ids)
            if len(props) < 2:
                raise ValueError("请至少选择 2 套有效房源进行对比")
            return props

        if cart_agent is None:
            raise ValueError("购物车对比需要提供 cart_agent")
        _cart, items = await cart_agent.get_cart_items(user_id)
        if not items:
            raise ValueError("购物车为空，请先添加房源再对比")

        props = await self._load_properties([item.property_id for item in items])
        if not props:
            raise ValueError("购物车中的房源已不存在")
        return props

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
        props = await self._resolve_compare_properties(
            user_id, property_ids, cart_agent
        )
        return await self._compare_props(props, priority)

    async def compare_stream(
        self,
        user_id: int,
        property_ids: list[int] | None = None,
        priority: str | None = None,
        cart_agent: CartService | None = None,
    ):
        """对比卡片使用确定性计算，用户可见说明直接透传上游 LLM token。"""
        props = await self._resolve_compare_properties(
            user_id, property_ids, cart_agent
        )
        normalized_priority = normalize_priority(priority)
        metrics, extras = await self._gather_compare_metrics(props)
        scores = compute_scores(metrics, normalized_priority)
        structured = self._rule_based_compare(
            props, scores, extras, normalized_priority
        )

        fact_lines: list[str] = []
        for index, prop in enumerate(props, 1):
            data = property_to_dict(prop)
            extra = extras[prop.id]
            score = scores[prop.id]
            fact_lines.append(
                f"{index}. {data['title']} [property_id={prop.id}] | "
                f"月租 {format_property_money(prop, data['price_monthly'])} | "
                f"{data['bedrooms']}室{data['bathrooms']}卫 | "
                f"面积 {data['area_sqm'] or '暂无数据'}㎡ | "
                f"通勤 {extra['commute'] or '暂无数据'} | "
                f"评价 {extra['rating'] if extra['rating'] is not None else '暂无数据'} | "
                f"综合得分 {score['total']} | "
                + " ".join(
                    f"{DIMENSION_LABELS[key]} {value}"
                    for key, value in score["breakdown"].items()
                )
            )

        reply = ""
        stream_failed = False
        if self.llm_service.is_available:
            try:
                async for token in self.llm_service.complete_text_stream(
                    [
                        {"role": "system", "content": COMPARE_STREAM_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"用户优先级：{PRIORITY_LABELS[normalized_priority]}\n\n"
                                + "\n".join(fact_lines)
                            ),
                        },
                    ],
                    temperature=0.3,
                    max_tokens=900,
                ):
                    if not token:
                        continue
                    reply += token
                    yield {"type": "token", "text": token}
            except Exception:
                stream_failed = True
                logger.exception("LLM 流式对比说明中断，降级为确定性分析")

        if not reply or stream_failed:
            fallback = str(
                structured.get("dimension_analysis") or structured["summary"]
            )
            continuation = f"\n\n{fallback}" if reply else fallback
            reply += continuation
            yield {"type": "token", "text": continuation}
            structured["ai_available"] = False
        else:
            structured["ai_available"] = True
            structured["summary"] = reply
            structured["dimension_analysis"] = reply

        yield {
            "type": "meta",
            "reply": reply,
            **structured,
        }

    # ── 指标聚合 ──────────────────────────────────────────────────

    async def _gather_compare_metrics(
        self, props: list[Property]
    ) -> tuple[list[PropertyMetrics], dict[int, dict]]:
        """为对比补充真实数据：POI 通勤距离 + 机构评价聚合。"""
        ids = [p.id for p in props]

        pois: dict[int, PropertyPOI] = {}
        try:
            # 可选周边字段缺失时只回滚 savepoint，不污染整轮 Agent 会话。
            async with self.session.begin_nested():
                rows = await self.session.scalars(
                    select(PropertyPOI)
                    .options(load_only(
                        PropertyPOI.id,
                        PropertyPOI.property_id,
                        PropertyPOI.content,
                        PropertyPOI.poi_data,
                        PropertyPOI.generated_at,
                        PropertyPOI.reviewed,
                        PropertyPOI.map_poi_data,
                        PropertyPOI.created_at,
                        PropertyPOI.updated_at,
                    ))
                    .where(PropertyPOI.property_id.in_(ids))
                )
                pois = {poi.property_id: poi for poi in rows}
        except Exception:
            logger.exception("加载 POI 数据失败，通勤维度取中性分")

        rating_by_inst: dict[int, tuple[float, int]] = {}
        inst_ids = {p.institute_id for p in props if p.institute_id}
        if inst_ids:
            try:
                async with self.session.begin_nested():
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
                    price=comparable_price_cny(p),
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
                        f"月租: {format_property_money(p, d['price_monthly'])} | "
                        f"户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
                        f"面积: {d['area_sqm'] or '未知'}㎡ | 通勤: {e['commute'] or '无数据'} | "
                        f"设施: {'、'.join(d['amenities']) if d['amenities'] else '无数据'} | "
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

        currencies = {property_currency(p) for p in props}
        if len(currencies) == 1:
            cheapest = min(props, key=lambda p: float(p.price_monthly))
            priciest = max(props, key=lambda p: float(p.price_monthly))
            price_summary = (
                f"价格区间 {format_property_money(cheapest, cheapest.price_monthly)} - "
                f"{format_property_money(priciest, priciest.price_monthly)}。"
            )
        else:
            price_summary = "包含多个币种，价格得分已统一换算后比较。"
        winner = max(props, key=lambda p: scores[p.id]["total"])
        fake_result = {
            "summary": (
                f"按「{PRIORITY_LABELS[priority]}」共对比 {len(props)} 套房源，"
                f"{price_summary}{AI_UNAVAILABLE_HINT}"
            ),
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

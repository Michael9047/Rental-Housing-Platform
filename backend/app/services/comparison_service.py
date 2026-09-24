"""独立户型对比服务 —— 复用 CompareAgent 的确定性五维评分与解释。"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agentic.agents.compare_agent import CompareAgent
from app.services.compare_scoring import (
    PRIORITY_LABELS,
    currencies_are_comparable,
    normalize_priority,
    parse_distance_meters,
)


class ComparisonService:
    """为 /compare/sessions 提供可持久化的 2-5 户型对比结果。"""

    def __init__(self, session: AsyncSession) -> None:
        self.db = session

    async def analyze(
        self,
        property_ids: list[int],
        user_message: str,
        priority: str = "balanced",
        conversation_history: list[dict[str, Any]] | None = None,
        token_sink: Callable[[str], Awaitable[None]] | None = None,
        status_sink: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """执行对比；流式调用方可直接接收模型原始 token。"""
        unit_type_ids = list(dict.fromkeys(property_ids))
        if not 2 <= len(unit_type_ids) <= 5:
            raise ValueError("请选择 2-5 个户型进行对比")

        effective_priority = _infer_priority(user_message, priority)
        compared = await CompareAgent(session=self.db).compare(
            user_id=0,
            property_ids=unit_type_ids,
            priority=effective_priority,
            token_sink=token_sink,
            status_sink=status_sink,
        )
        scores: dict[int, dict] = {}
        property_data: dict[int, dict] = {}
        for item in compared["items"]:
            unit_type = item["property"]
            institute = unit_type.institute
            scores[item["property_id"]] = {
                "total": item["score"],
                "breakdown": item.get("score_breakdown") or {},
            }
            property_data[item["property_id"]] = {
                # 对外字段名兼容旧前端，ID 语义为 UnitType.id。
                "property_id": unit_type.id,
                "unit_type_id": unit_type.id,
                "institute_id": unit_type.institute_id,
                "institute_name": institute.name_cn or institute.name,
                "title": item["title"],
                "name": unit_type.name,
                "district": institute.district,
                "address": institute.address,
                "institute_address": institute.address,
                "country": institute.country,
                "city": institute.city,
                "price_monthly": float(unit_type.base_rent),
                "base_rent": float(unit_type.base_rent),
                "currency": unit_type.currency,
                "area_sqm": float(unit_type.area_sqm) if unit_type.area_sqm is not None else None,
                "bedrooms": unit_type.bedrooms,
                "bathrooms": unit_type.bathrooms,
                "property_type": (
                    unit_type.property_type.value
                    if hasattr(unit_type.property_type, "value") else unit_type.property_type
                ),
                "amenities": list(dict.fromkeys([
                    *list(unit_type.amenities or []),
                    *list(institute.amenities or []),
                ])),
                "deposit_amount": unit_type.deposit_amount,
                "deposit_type": (
                    unit_type.deposit_type.value
                    if hasattr(unit_type.deposit_type, "value") else unit_type.deposit_type
                ),
                "min_lease_months": unit_type.min_stay_months,
                "min_stay_months": unit_type.min_stay_months,
                "has_vacancy": unit_type.has_vacancy,
                "available_count": unit_type.available_count,
                "total_count": unit_type.total_count,
                "image_urls": list(unit_type.image_urls or []),
                "image_count": len(unit_type.image_urls or []),
                "transit_display": item.get("commute"),
                "rating": item.get("rating"),
                "review_count": item.get("review_count", 0),
                "safety_score": item.get("safety_score"),
            }

        base_reply = compared.get("dimension_analysis") or compared["summary"]
        is_initial = user_message.strip() in {"", "请对比分析这些户型", "请对比分析这些房源"}
        focused_reply, focuses = _build_question_focused_reply(
            user_message,
            property_data,
            effective_priority,
            conversation_history,
        )
        if is_initial:
            reply = base_reply
        elif focused_reply:
            reply = focused_reply
        else:
            reply = (
                f"针对你的追问“{user_message.strip()}”，我已按「{PRIORITY_LABELS[effective_priority]}」"
                f"重新计算并整理现有真实数据：\n\n{base_reply}"
            )
        return {
            "reply": reply,
            "scores": scores,
            "tool_trail": [{
                "tool": "compare_unit_types",
                "status": "success",
                "unit_type_ids": unit_type_ids,
                "priority": compared.get("priority", effective_priority),
                "question_focus": focuses,
            }],
            "property_data": property_data,
            "priority": effective_priority,
            "_reply_streamed": bool(compared.get("_reply_streamed")),
        }


def _infer_priority(message: str, fallback: str) -> str:
    """让追问中的明确侧重点真正改变本轮确定性评分。"""
    text = message.lower()
    patterns = (
        ("safety", ("安全", "治安", "犯罪")),
        ("commute", ("通勤", "学校", "地铁", "距离", "时间")),
        ("budget", ("预算", "便宜", "价格", "租金", "省钱")),
        ("space", ("空间", "面积", "宽敞", "卧室")),
    )
    for candidate, keywords in patterns:
        if any(keyword in text for keyword in keywords):
            return candidate
    return normalize_priority(fallback)


_AMENITY_TERMS = (
    "健身房", "泳池", "独立卫浴", "独卫", "空调", "洗衣机", "厨房",
    "电梯", "门禁", "安保", "停车", "车位", "阳台", "WiFi", "wifi",
)


def _detect_focuses(text: str) -> list[str]:
    """识别追问关注点；只决定展示维度，不生成或修改任何房源事实。"""
    lowered = text.casefold()
    signals = (
        ("amenities", (*_AMENITY_TERMS, "设施", "配套")),
        ("lease", ("长期", "短租", "租期", "几个月", "最短入住")),
        ("safety", ("安全", "治安", "犯罪")),
        ("commute", ("通勤", "学校", "地铁", "公交", "交通", "距离")),
        ("budget", ("预算", "便宜", "价格", "租金", "省钱", "性价比")),
        ("space", ("空间", "面积", "宽敞", "卧室", "几室")),
        ("rating", ("评价", "评分", "口碑", "评论")),
    )
    return [name for name, keywords in signals if any(keyword.casefold() in lowered for keyword in keywords)]


def _build_question_focused_reply(
    question: str,
    property_data: dict[int, dict],
    priority: str,
    conversation_history: list[dict[str, Any]] | None,
) -> tuple[str | None, list[str]]:
    """根据真实字段回答追问；历史只用于补足“那这个呢”等省略问法。"""
    focuses = _detect_focuses(question)
    if not focuses:
        for message in reversed(conversation_history or []):
            if message.get("role") != "user":
                continue
            previous = str(message.get("content") or "").strip()
            if not previous or previous == question.strip():
                continue
            focuses = _detect_focuses(previous)
            if focuses:
                break
    if not focuses:
        return None, []

    sections: list[str] = []
    for focus in focuses:
        builder = _FOCUS_BUILDERS[focus]
        sections.append(builder(question, property_data))
    intro = (
        f"针对你的追问“{question.strip()}”，我按「{PRIORITY_LABELS[priority]}」权重重新计算，"
        "并只使用当前户型与公寓记录回答："
    )
    return intro + "\n\n" + "\n\n".join(sections), focuses


def _title(data: dict) -> str:
    return str(data.get("title") or data.get("name") or f"户型 #{data.get('property_id')}")


def _money(data: dict) -> str:
    currency = str(data.get("currency") or "未知币种").upper()
    symbols = {"GBP": "£", "SGD": "S$", "USD": "$", "HKD": "HK$", "CNY": "¥"}
    amount = data.get("base_rent")
    if amount is None:
        return "租金未知"
    return f"{symbols.get(currency, currency + ' ')}{float(amount):g}/月"


def _budget_section(_question: str, property_data: dict[int, dict]) -> str:
    rows = list(property_data.values())
    lines = ["### 价格与预算"]
    lines.extend(f"- **{_title(data)}**：{_money(data)}" for data in rows)
    priced = [data for data in rows if data.get("base_rent") is not None]
    price_comparable = (
        len(priced) == len(rows)
        and currencies_are_comparable(data.get("currency") for data in rows)
    )
    if not price_comparable:
        lines.append("- 结论：币种缺失或不一致，不直接比较租金高低；请先确认币种与统一换算口径。")
    elif priced:
        cheapest = min(priced, key=lambda data: float(data["base_rent"]))
        lines.append(f"- 结论：按当前同币种月租，**{_title(cheapest)}** 最低（{_money(cheapest)}）。")
    else:
        lines.append("- 结论：当前缺少可比较的租金数据。")
    return "\n".join(lines)


def _commute_section(_question: str, property_data: dict[int, dict]) -> str:
    rows = list(property_data.values())
    lines = ["### 通勤与交通"]
    known: list[tuple[int, dict]] = []
    for data in rows:
        display = data.get("transit_display")
        lines.append(f"- **{_title(data)}**：{display or '暂无交通距离数据'}")
        distance = parse_distance_meters(display)
        if distance is not None:
            known.append((distance, data))
    if known:
        best = min(known, key=lambda item: item[0])[1]
        lines.append(f"- 结论：按“最近交通站点距离”，**{_title(best)}** 最有优势；这不是到学校的门到门时间。")
    else:
        lines.append("- 结论：当前没有足够的真实交通距离，无法判断通勤最优。")
    return "\n".join(lines)


def _space_section(_question: str, property_data: dict[int, dict]) -> str:
    rows = list(property_data.values())
    lines = ["### 空间与户型"]
    known: list[dict] = []
    for data in rows:
        area = data.get("area_sqm")
        area_text = f"{float(area):g}㎡" if area is not None else "面积未知"
        lines.append(
            f"- **{_title(data)}**：{area_text}，{data.get('bedrooms', 0)}室{data.get('bathrooms', 0)}卫"
        )
        if area is not None:
            known.append(data)
    if known:
        largest = max(known, key=lambda data: float(data["area_sqm"]))
        lines.append(f"- 结论：按已登记面积，**{_title(largest)}** 最大。")
    else:
        lines.append("- 结论：所有候选都缺少面积，无法判断哪套更宽敞。")
    return "\n".join(lines)


def _safety_section(_question: str, property_data: dict[int, dict]) -> str:
    rows = list(property_data.values())
    lines = ["### 安全与治安"]
    known: list[dict] = []
    for data in rows:
        score = data.get("safety_score")
        lines.append(
            f"- **{_title(data)}**：{f'{float(score):g}/5' if score is not None else '暂无安全评分'}"
        )
        if score is not None:
            known.append(data)
    if known:
        safest = max(known, key=lambda data: float(data["safety_score"]))
        lines.append(f"- 结论：按现有安全评分，**{_title(safest)}** 最高。")
    else:
        lines.append("- 结论：当前候选均无安全数据，不能据此判断治安优劣。")
    return "\n".join(lines)


def _amenities_section(question: str, property_data: dict[int, dict]) -> str:
    rows = list(property_data.values())
    requested = [term for term in _AMENITY_TERMS if term.casefold() in question.casefold()]
    requested = list(dict.fromkeys("WiFi" if term.casefold() == "wifi" else term for term in requested))
    lines = ["### 设施与配套"]
    matching: list[dict] = []
    for data in rows:
        amenities = [str(value) for value in (data.get("amenities") or [])]
        lines.append(f"- **{_title(data)}**：{'、'.join(amenities) if amenities else '暂无已登记设施'}")
        if requested and all(
            any(term.casefold() in amenity.casefold() for amenity in amenities)
            for term in requested
        ):
            matching.append(data)
    if requested and matching:
        names = "、".join(f"**{_title(data)}**" for data in matching)
        lines.append(f"- 结论：明确记录有{'、'.join(requested)}的是 {names}。")
    elif requested:
        lines.append(
            f"- 结论：现有记录未确认哪套具备{'、'.join(requested)}；“未登记”不等于“一定没有”，建议向公寓确认。"
        )
    return "\n".join(lines)


def _lease_section(question: str, property_data: dict[int, dict]) -> str:
    rows = list(property_data.values())
    lines = ["### 租期与长期居住"]
    known: list[dict] = []
    for data in rows:
        months = data.get("min_stay_months")
        lines.append(
            f"- **{_title(data)}**：{f'最短租期 {months} 个月' if months is not None else '最短租期未知'}"
        )
        if months is not None:
            known.append(data)
    if "短租" in question and known:
        flexible = min(known, key=lambda data: int(data["min_stay_months"]))
        lines.append(f"- 结论：按最短租期，**{_title(flexible)}** 对短租更灵活。")
    else:
        lines.append(
            "- 结论：main 当前只记录最短租期，没有最长租期或续租承诺；长期住还应结合设施、空间和续租政策确认。"
        )
    return "\n".join(lines)


def _rating_section(_question: str, property_data: dict[int, dict]) -> str:
    rows = list(property_data.values())
    lines = ["### 评价与口碑"]
    known: list[dict] = []
    for data in rows:
        rating = data.get("rating")
        count = int(data.get("review_count") or 0)
        lines.append(
            f"- **{_title(data)}**：{f'{float(rating):g}/5（{count} 条）' if rating is not None else '暂无已审核评价'}"
        )
        if rating is not None:
            known.append(data)
    if known:
        best = max(known, key=lambda data: float(data["rating"]))
        lines.append(f"- 结论：按现有已审核评分，**{_title(best)}** 最高。")
    else:
        lines.append("- 结论：当前没有足够评价数据，无法判断口碑最好。")
    return "\n".join(lines)


_FOCUS_BUILDERS = {
    "budget": _budget_section,
    "commute": _commute_section,
    "space": _space_section,
    "safety": _safety_section,
    "amenities": _amenities_section,
    "lease": _lease_section,
    "rating": _rating_section,
}

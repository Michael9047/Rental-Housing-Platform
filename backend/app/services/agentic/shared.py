"""Agent 共享工具函数 —— 从 AgentService 提取，供多个 Agent 复用。"""
from __future__ import annotations

import re
from typing import Any

from app.models.unit_type import UnitType
from app.services.compare_scoring import DIMENSION_LABELS, currencies_are_comparable


INCOMPARABLE_PRICE_SUMMARY = (
    "候选币种缺失或不一致，原始月租仅并列展示，价格维度按中性分处理。"
)
INCOMPARABLE_PRICE_RECOMMENDATION = (
    "当前建议不依据租金高低；请先确认所有候选的币种和统一换算口径，再做价格决策。"
)
_RELATIVE_PRICE_CLAIM = re.compile(
    r"最便宜|更便宜|较便宜|最贵|更贵|较贵|最低价|最高价|"
    r"价格(?:最低|最高|偏高|偏低|更高|更低|较高|较低|最有优势)|"
    r"性价比|最划算|更划算"
)


def guard_price_narrative(
    summary: str,
    recommendation: str,
    currencies: list[str | None],
) -> tuple[str, str]:
    """LLM 只能在价格可比时输出价格结论；否则改用确定性安全文本。"""
    if currencies_are_comparable(currencies):
        return summary, recommendation
    return INCOMPARABLE_PRICE_SUMMARY, INCOMPARABLE_PRICE_RECOMMENDATION


def guard_price_item_narratives(
    pros: list[str],
    cons: list[str],
    currencies: list[str | None],
) -> tuple[list[str], list[str]]:
    """币种不可比时删除 LLM 单卡中的相对价格判断，保留绝对租金事实。"""
    if currencies_are_comparable(currencies):
        return pros, cons
    return (
        [claim for claim in pros if not _RELATIVE_PRICE_CLAIM.search(claim)],
        [claim for claim in cons if not _RELATIVE_PRICE_CLAIM.search(claim)],
    )


def unit_type_title(unit_type: UnitType) -> str:
    """返回带公寓名的户型标题。"""
    institute = getattr(unit_type, "institute", None)
    institute_name = getattr(institute, "name_cn", None) or getattr(institute, "name", None)
    return " · ".join(part for part in (institute_name, unit_type.name) if part)


def format_unit_type_money(unit_type: UnitType, value: float) -> str:
    """按户型真实币种格式化金额。"""
    currency = str(unit_type.currency or "").upper()
    if not currency:
        return f"{value:.0f}（币种未知）"
    symbol = {"GBP": "£", "SGD": "S$", "USD": "$", "HKD": "HK$", "CNY": "¥"}.get(
        currency, f"{currency} "
    )
    return f"{symbol}{value:.0f}"


def property_to_dict(prop: UnitType) -> dict[str, Any]:
    """将 UnitType + Institute 转为 LLM 上下文（仅真实字段）。"""
    institute = getattr(prop, "institute", None)
    property_type = prop.property_type
    return {
        "property_id": prop.id,
        "title": unit_type_title(prop),
        "district": getattr(institute, "district", None),
        "address": getattr(institute, "address", None),
        "currency": prop.currency,
        "price_monthly": float(prop.base_rent),
        "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "property_type": property_type.value if hasattr(property_type, "value") else str(property_type or ""),
        "description": (prop.description or "")[:200],
        "amenities": list(prop.amenities or []),
        "institute_id": prop.institute_id,
    }


def build_dimension_analysis(
    props: list[UnitType],
    scores: dict[int, dict],
    extras: dict[int, dict],
    priority: str,
    llm_result: dict[str, Any] | None = None,
) -> str:
    """用真实数据构建按维度组织的对比分析 Markdown（确定性输出，非 LLM）。

    维度顺序：通勤 → 周边配套 → 房内设施 → 价格 → 空间 → 评价与安全 → 综合推荐
    """
    by_id = {p.id: p for p in props}
    lines: list[str] = []

    summary = str((llm_result or {}).get("summary", "")) if llm_result else ""
    recommendation = str((llm_result or {}).get("recommendation", "")) if llm_result else ""
    summary, recommendation = guard_price_narrative(
        summary, recommendation, [p.currency for p in props]
    )
    if summary:
        lines.append(f"> {summary}\n")

    lines.append("## 📊 多维度对比分析\n")

    # 1. 通勤交通
    lines.append("### 🚇 通勤交通")
    sorted_commute = sorted(props, key=lambda p: (
        float("inf") if extras[p.id].get("commute") is None
        else parse_commute_meters(extras[p.id].get("commute", ""))
    ))
    for p in sorted_commute:
        c = extras[p.id].get("commute") or "暂无数据"
        s = scores[p.id]["breakdown"].get("commute", 0)
        lines.append(f"- **{unit_type_title(p)}**：{c}（通勤得分 {s}）")
    if sorted_commute:
        best = sorted_commute[0]
        if extras[best.id].get("commute"):
            lines.append(f"\n✅ 通勤最优：**{unit_type_title(best)}**\n")

    # 2. 周边配套
    lines.append("### 🏪 周边配套")
    for p in props:
        d = property_to_dict(p)
        district_info = d.get("district", "未知区域")
        desc = (d.get("description") or "")[:120]
        facility_hints = extract_facility_hints(desc)
        hint_text = f"（{'、'.join(facility_hints)}）" if facility_hints else ""
        lines.append(f"- **{unit_type_title(p)}**：位于{district_info}{hint_text}")
    lines.append("")

    # 3. 房内设施
    lines.append("### 🛋️ 房内设施")
    for p in props:
        desc = (p.description or "")[:200]
        amenities = list(p.amenities or []) or extract_amenities_from_desc(desc)
        if amenities:
            lines.append(f"- **{unit_type_title(p)}**：{'、'.join(amenities)}")
        else:
            lines.append(f"- **{unit_type_title(p)}**：设施信息待补充（请联系公寓确认）")
    lines.append("")

    # 4. 价格对比
    lines.append("### 💰 价格对比")
    price_comparable = currencies_are_comparable(p.currency for p in props)
    sorted_price = (
        sorted(props, key=lambda p: float(p.base_rent))
        if price_comparable else list(props)
    )
    for p in sorted_price:
        s = scores[p.id]["breakdown"].get("price", 0)
        deposit = getattr(p, "deposit_amount", None)
        deposit_text = f"（押金 {format_unit_type_money(p, float(deposit))}）" if deposit else ""
        rent_text = format_unit_type_money(p, float(p.base_rent))
        lines.append(f"- **{unit_type_title(p)}**：{rent_text}/月 {deposit_text}（价格得分 {s}）")
    if price_comparable:
        cheapest = sorted_price[0]
        lines.append(
            f"\n💰 价格最低：**{unit_type_title(cheapest)}**"
            f"（{format_unit_type_money(cheapest, float(cheapest.base_rent))}/月）\n"
        )
    else:
        lines.append("\nℹ️ 候选币种缺失或不一致，未直接比较租金高低；请先确认币种与换算口径。\n")

    # 5. 空间户型
    lines.append("### 📐 空间户型")
    sorted_space = sorted(props, key=lambda p: float(p.area_sqm or 0), reverse=True)
    for p in sorted_space:
        s = scores[p.id]["breakdown"].get("space", 0)
        area = f"{p.area_sqm}㎡" if p.area_sqm else "未知"
        lines.append(f"- **{unit_type_title(p)}**：{area}，{p.bedrooms}室{p.bathrooms}卫（空间得分 {s}）")
    known_space = [p for p in sorted_space if p.area_sqm is not None]
    if known_space:
        max_area = float(known_space[0].area_sqm)
        largest = [p for p in known_space if float(p.area_sqm) == max_area]
        if len(largest) == 1:
            lines.append(f"\n📐 空间最大：**{unit_type_title(largest[0])}**\n")
        else:
            names = "、".join(f"**{unit_type_title(p)}**" for p in largest)
            lines.append(f"\n📐 已知面积并列最大：{names}（{max_area:g}㎡）\n")
    else:
        lines.append("\nℹ️ 候选均缺少面积数据，暂时无法比较空间大小。\n")

    # 6. 评价与安全
    lines.append("### ⭐ 评价与安全")
    for p in props:
        e = extras[p.id]
        if e.get("rating") is not None:
            rating_text = f"★ {e['rating']:.1f}（{e['review_count']}条评价）"
        else:
            rating_text = "暂无评价数据"
        safety_text = (
            f"安全 {e['safety_score']:.1f}/5"
            if e.get("safety_score") is not None else "暂无安全数据"
        )
        lines.append(f"- **{unit_type_title(p)}**：{rating_text}；{safety_text}")
    lines.append("")

    # 7. 综合排序与推荐
    lines.append("### 🏆 综合排序")
    sorted_total = sorted(props, key=lambda p: scores[p.id]["total"], reverse=True)
    rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for rank, p in enumerate(sorted_total):
        emoji = rank_emoji[rank] if rank < len(rank_emoji) else f"{rank+1}."
        total = scores[p.id]["total"]
        bd = scores[p.id]["breakdown"]
        dim_parts = [f"{DIMENSION_LABELS.get(k, k)} {v}" for k, v in bd.items()]
        lines.append(f"{emoji} **{unit_type_title(p)}** — {total} 分（{' | '.join(dim_parts)}）")

    if recommendation:
        lines.append(f"\n💡 {recommendation}")

    return "\n".join(lines)


def parse_commute_meters(commute_text: str) -> float:
    """从通勤文本中提取米数，用于排序。"""
    import re
    # 先匹配 km；否则 ``1.5km`` 会被米制正则误读成 ``5m``。
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|公里|千米)", commute_text, re.IGNORECASE)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|米)(?![a-z])", commute_text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 10000


def extract_facility_hints(description: str) -> list[str]:
    """从房源描述中提取周边设施关键词。"""
    hints = []
    keywords = {
        "地铁": "近地铁", "公交": "近公交", "超市": "近超市",
        "商场": "近商场", "餐厅": "有餐厅", "公园": "近公园",
        "医院": "近医院", "学校": "近学校", "NUS": "近NUS",
        "商圈": "商圈附近", "步行": "步行可达",
    }
    for kw, label in keywords.items():
        if kw in description:
            hints.append(label)
    return hints[:5]


def extract_amenities_from_desc(description: str) -> list[str]:
    """从房源描述中提取设施关键词。"""
    amenities = []
    amenity_kw = {
        "WiFi": "WiFi", "wifi": "WiFi", "空调": "空调", "暖气": "暖气",
        "洗衣机": "洗衣机", "冰箱": "冰箱", "阳台": "阳台",
        "厨房": "厨房", "独立卫浴": "独立卫浴", "独卫": "独立卫浴",
        "电梯": "电梯", "车位": "车位", "停车": "车位",
        "健身房": "健身房", "泳池": "泳池", "家具": "家具齐全",
        "拎包": "拎包入住", "精装": "精装修",
    }
    for kw, label in amenity_kw.items():
        if kw in description:
            if label not in amenities:
                amenities.append(label)
    return amenities

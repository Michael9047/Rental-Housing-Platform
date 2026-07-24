"""Agent 共享工具函数 —— 从 AgentService 提取，供多个 Agent 复用。"""
from __future__ import annotations

from typing import Any

from app.models.property import Property
from app.services.compare_scoring import DIMENSION_LABELS


def property_to_dict(prop: Property) -> dict[str, Any]:
    """将 Property ORM 转为 LLM 上下文用的 dict（仅真实字段）。"""
    return {
        "property_id": prop.id,
        "title": prop.title,
        "district": prop.district,
        "address": prop.address,
        "currency": getattr(prop, 'currency', None),
        "price_monthly": float(prop.price_monthly),
        "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "property_type": prop.property_type.value if hasattr(prop.property_type, "value") else str(prop.property_type),
        "description": (prop.description or "")[:200],
    }


def build_dimension_analysis(
    props: list[Property],
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

    summary = (llm_result or {}).get("summary", "") if llm_result else ""
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
        lines.append(f"- **{p.title}**：{c}（通勤得分 {s}）")
    if sorted_commute:
        best = sorted_commute[0]
        if extras[best.id].get("commute"):
            lines.append(f"\n✅ 通勤最优：**{best.title}**\n")

    # 2. 周边配套
    lines.append("### 🏪 周边配套")
    for p in props:
        d = property_to_dict(p)
        district_info = d.get("district", "未知区域")
        desc = (d.get("description") or "")[:120]
        facility_hints = extract_facility_hints(desc)
        hint_text = f"（{'、'.join(facility_hints)}）" if facility_hints else ""
        lines.append(f"- **{p.title}**：位于{district_info}{hint_text}")
    lines.append("")

    # 3. 房内设施
    lines.append("### 🛋️ 房内设施")
    for p in props:
        desc = (p.description or "")[:200]
        amenities = extract_amenities_from_desc(desc)
        if amenities:
            lines.append(f"- **{p.title}**：{'、'.join(amenities)}")
        else:
            lines.append(f"- **{p.title}**：设施信息待补充（请联系房东确认）")
    lines.append("")

    # 4. 价格对比
    lines.append("### 💰 价格对比")
    sorted_price = sorted(props, key=lambda p: float(p.price_monthly))
    for p in sorted_price:
        s = scores[p.id]["breakdown"].get("price", 0)
        deposit = getattr(p, "deposit_amount", None)
        deposit_text = f"（押金 ¥{float(deposit):.0f}）" if deposit else ""
        lines.append(f"- **{p.title}**：¥{float(p.price_monthly):.0f}/月 {deposit_text}（价格得分 {s}）")
    lines.append(f"\n💰 价格最低：**{sorted_price[0].title}**（¥{float(sorted_price[0].price_monthly):.0f}/月）\n")

    # 5. 空间户型
    lines.append("### 📐 空间户型")
    sorted_space = sorted(props, key=lambda p: float(p.area_sqm or 0), reverse=True)
    for p in sorted_space:
        s = scores[p.id]["breakdown"].get("space", 0)
        area = f"{p.area_sqm}㎡" if p.area_sqm else "未知"
        lines.append(f"- **{p.title}**：{area}，{p.bedrooms}室{p.bathrooms}卫（空间得分 {s}）")
    lines.append(f"\n📐 空间最大：**{sorted_space[0].title}**\n")

    # 6. 评价与安全
    lines.append("### ⭐ 评价与安全")
    for p in props:
        e = extras[p.id]
        if e.get("rating") is not None:
            lines.append(f"- **{p.title}**：★ {e['rating']:.1f}（{e['review_count']}条评价）")
        else:
            lines.append(f"- **{p.title}**：暂无评价数据")
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
        lines.append(f"{emoji} **{p.title}** — {total} 分（{' | '.join(dim_parts)}）")

    recommendation = (llm_result or {}).get("recommendation", "") if llm_result else ""
    if recommendation:
        lines.append(f"\n💡 {recommendation}")

    return "\n".join(lines)


def parse_commute_meters(commute_text: str) -> float:
    """从通勤文本中提取米数，用于排序。"""
    import re
    m = re.search(r"(\d+)\s*[m米]", commute_text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+\.?\d*)\s*[kK][mM]", commute_text)
    if m:
        return float(m.group(1)) * 1000
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

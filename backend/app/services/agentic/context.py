"""上下文管理 —— 滑动窗口、确定性摘要与带来源的候选打包。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatMessageRole


DEFAULT_HISTORY_CHAR_BUDGET = 8_000
DEFAULT_CANDIDATE_CHAR_BUDGET = 12_000


async def load_packed_history(
    session: AsyncSession,
    session_id: int,
    *,
    rolling_summary: str | None = None,
    max_messages: int = 12,
    char_budget: int = DEFAULT_HISTORY_CHAR_BUDGET,
) -> list[dict[str, str]]:
    """在预算内保留最近消息，并用状态摘要替代过旧内容。"""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(max(max_messages * 3, 24))
    )
    rows = list(await session.scalars(stmt))
    selected: list[dict[str, str]] = []
    used_chars = 0
    for row in rows:
        if row.role not in (ChatMessageRole.user, ChatMessageRole.assistant):
            continue
        content = (row.content or "").strip()
        if not content:
            continue
        # 单条过长回复只保留开头和结尾，房源事实由 state/search run 提供。
        if len(content) > 1_200:
            content = f"{content[:850]}\n…（中间内容已压缩）…\n{content[-250:]}"
        if selected and (used_chars + len(content) > char_budget or len(selected) >= max_messages):
            break
        selected.append({"role": row.role.value, "content": content})
        used_chars += len(content)
    selected.reverse()
    if rolling_summary:
        selected.insert(0, {
            "role": "assistant",
            "content": f"[历史状态摘要，仅作上下文，不是用户新消息] {rolling_summary[:1600]}",
        })
    return selected


def pack_grounded_candidates(
    *,
    query: str,
    stage: str,
    filters: dict[str, Any],
    candidates: list[dict[str, Any]],
    school: str,
    currency: str,
    relaxation_trace: list[dict[str, Any]],
    unresolved_constraints: list[str] | None = None,
    max_candidates: int = 5,
    char_budget: int = DEFAULT_CANDIDATE_CHAR_BUDGET,
) -> dict[str, Any]:
    """只向生成模型提供可追溯事实，按名次和字符预算截断。"""
    packed: dict[str, Any] = {
        "query": query,
        "stage": stage,
        "school": school,
        "currency": currency,
        "effective_filters": filters,
        "total_candidates": len(candidates),
        "relaxation_trace": relaxation_trace,
        "unresolved_constraints": unresolved_constraints or [],
        "grounding_policy": {
            "allowed": "只可使用 candidates.facts 中的值",
            "missing": "值为 null 或来源为 missing 时必须说暂无数据",
            "identity": "只能提及 candidates 中给出的 id 和名称",
        },
        "candidates": [],
    }
    for item in candidates[:max_candidates]:
        unit_type = item["unit_type"]
        institute = item["institute"]
        candidate = {
            "rank": int(item.get("_rank", len(packed["candidates"]) + 1)),
            "id": int(item.get("_property_id", unit_type.id)),
            "unit_type_id": item.get("_unit_type_id"),
            "facts": {
                "name": unit_type.name,
                "institute": institute.name,
                "district": institute.district,
                "address": institute.address,
                "price": float(unit_type.base_rent),
                "currency": unit_type.currency,
                "bedrooms": unit_type.bedrooms,
                "bathrooms": unit_type.bathrooms,
                "area_sqm": float(unit_type.area_sqm) if unit_type.area_sqm is not None else None,
                "available_rooms": int(item.get("available_rooms", 0) or 0),
                "available_from": str(unit_type.available_from) if unit_type.available_from else None,
                "min_stay_months": unit_type.min_stay_months,
                "institute_amenities": institute.amenities or [],
                "unit_amenities": unit_type.amenities or [],
                "description": (unit_type.description or institute.description or "")[:260] or None,
                "special_offer": unit_type.special_offer,
                "commute_minutes": item.get("_commute_minutes"),
                "poi_distances_m": item.get("_poi_distances") or {},
            },
            "sources": item.get("_source_metadata") or {},
        }
        projected = len(str(packed)) + len(str(candidate))
        if packed["candidates"] and projected > char_budget:
            break
        packed["candidates"].append(candidate)
    return packed


def user_facing_sources(source_manifest: dict[str, Any]) -> list[dict[str, str]]:
    """把内部表名收敛成用户能理解的来源标签。"""
    rows = source_manifest.get("sources") if isinstance(source_manifest, dict) else []
    if not isinstance(rows, list) or not rows:
        return []
    available: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("property") != "missing":
            available.add("房源基础信息")
        if row.get("inventory") != "missing":
            available.add("实时库存")
        if row.get("commute") != "missing":
            available.add("通勤数据")
        if row.get("poi") != "missing":
            available.add("周边设施")
        if row.get("semantic") != "missing":
            available.add("语义匹配")
    order = ("房源基础信息", "实时库存", "通勤数据", "周边设施", "语义匹配")
    return [
        {"label": label, "status": "verified"}
        for label in order if label in available
    ]

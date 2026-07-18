"""MoE 设施专家 —— 硬约束 AND 语义二次确认。

AmenityExpert 不调用 LLM，纯 Python 逻辑：
- 对 search_agent 返回的候选房源逐条检查硬约束设施
- AND 语义：用户要求的全部设施都必须存在，缺一不可
- 输出通过硬约束的候选 + 被排除的候选（带缺失原因）
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult

logger = logging.getLogger(__name__)

# 设施标准值列表（与 FilterAgent 保持一致）
_STANDARD_AMENITIES = {
    "宠物友好", "独立厨房", "独立卫浴", "空调", "洗衣机", "冰箱",
    "WiFi", "暖气", "阳台", "电梯", "车位", "健身房", "泳池",
    "自习室", "家具齐全", "精装修", "包水电", "禁烟",
}

# 设施同义词映射（用于宽松匹配，如 DB 中存了 "可养宠物" 而非 "宠物友好"）
_AMENITY_SYNONYMS: dict[str, set[str]] = {
    "宠物友好": {"宠物友好", "可养宠物", "能养宠物", "养猫", "养狗", "宠物", "pet friendly", "pet-friendly"},
    "独立厨房": {"独立厨房", "厨房", "开放厨房", "可做饭", "能做饭", "kitchen"},
    "独立卫浴": {"独立卫浴", "独卫", "独立卫生间", "私人卫生间", "ensuite"},
    "空调": {"空调", "冷气", "air conditioning", "ac"},
    "洗衣机": {"洗衣机", "洗衣", "烘干机", "washer", "laundry"},
    "冰箱": {"冰箱", "冰柜", "fridge", "refrigerator"},
    "WiFi": {"WiFi", "wifi", "无线网", "宽带", "网络", "上网", "internet"},
    "暖气": {"暖气", "地暖", "供暖", "取暖", "heating"},
    "阳台": {"阳台", "露台", "balcony"},
    "电梯": {"电梯", "有电梯", "elevator", "lift"},
    "车位": {"车位", "停车位", "停车场", "停车", "parking"},
    "健身房": {"健身房", "健身", "gym", "fitness"},
    "泳池": {"泳池", "游泳池", "游泳", "pool", "swimming"},
    "自习室": {"自习室", "自习", "学习室", "study room"},
    "家具齐全": {"家具齐全", "家具", "拎包", "拎包入住", "furnished"},
    "精装修": {"精装修", "精装", "装修好", "renovated"},
    "包水电": {"包水电", "包水电网", "全包", "utilities included"},
    "禁烟": {"禁烟", "无烟", "不吸烟", "禁止吸烟", "no smoking", "non-smoking"},
}


def _amenity_matches(property_amenities: list[str] | None, required: str) -> bool:
    """检查房源是否满足单个设施需求（宽松同义词匹配）。"""
    if not property_amenities:
        return False
    synonyms = _AMENITY_SYNONYMS.get(required, {required})
    prop_lower = {a.strip().lower() for a in property_amenities}
    for syn in synonyms:
        if syn.lower() in prop_lower:
            return True
    return False


def check_hard_constraints(
    candidates: list[dict[str, Any]],
    required_amenities: list[str],
    required_room_type: str | None = None,
    required_bathrooms: int | None = None,
) -> dict[str, Any]:
    """对候选房源逐条检查硬约束（AND 语义）。

    Args:
        candidates: 候选房源列表，每项包含 property 对象和可能的 amenities 列表
        required_amenities: 必须全部满足的设施列表
        required_room_type: 必须匹配的房型
        required_bathrooms: 最低卫生间数

    Returns:
        {
            "passed": [...],       # 通过硬约束的候选
            "excluded": [...],     # 被排除的候选，每项含 missing 字段
            "total": int,
            "passed_count": int,
            "excluded_count": int,
            "required": [...],     # 用户要求的硬约束列表
        }
    """
    passed: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for cand in candidates:
        prop = cand.get("property")
        missing: list[str] = []

        # 检查设施硬约束（AND 语义）
        if required_amenities:
            prop_amenities: list[str] | None = None
            if prop is not None and hasattr(prop, "amenities"):
                prop_amenities = prop.amenities
            elif isinstance(cand, dict) and "amenities" in cand:
                prop_amenities = cand["amenities"]

            for req_amenity in required_amenities:
                if not _amenity_matches(prop_amenities, req_amenity):
                    missing.append(req_amenity)

        # 检查房型硬约束
        if required_room_type and prop is not None:
            # 检查 property 级别
            if hasattr(prop, "property_type") and prop.property_type != required_room_type:
                # 也检查 room_types
                if hasattr(prop, "room_types") and prop.room_types:
                    room_type_values = {rt.room_type.value if hasattr(rt.room_type, "value") else str(rt.room_type)
                                        for rt in prop.room_types}
                    if required_room_type not in room_type_values:
                        missing.append(f"房型:{required_room_type}")
                else:
                    missing.append(f"房型:{required_room_type}")

        # 检查卫生间数硬约束
        if required_bathrooms is not None and prop is not None and hasattr(prop, "bathrooms"):
            if (prop.bathrooms or 0) < required_bathrooms:
                missing.append(f"卫生间≥{required_bathrooms}")

        if missing:
            excluded.append({**cand, "_missing_amenities": missing})
        else:
            passed.append(cand)

    total = len(candidates)
    result = {
        "passed": passed,
        "excluded": excluded,
        "total": total,
        "passed_count": len(passed),
        "excluded_count": len(excluded),
        "required_amenities": required_amenities,
        "required_room_type": required_room_type,
        "required_bathrooms": required_bathrooms,
    }

    if excluded:
        logger.info(
            "硬约束过滤: %d/%d 通过, 排除原因: %s",
            len(passed), total,
            {i: cand.get("_missing_amenities", []) for i, cand in enumerate(excluded[:5])},
        )

    return result


class AmenityExpert(BaseAgent):
    """设施硬约束专家 —— 纯 Python 逻辑，不调用 LLM。

    在 search_agent 之后执行，对候选房源做 AND 语义的设施检查。
    与 PriceExpert/CommuteExpert 等软评分专家不同，
    AmenityExpert 是硬过滤——不满足的房源直接排除。
    """

    name = "amenity_expert"
    description = "MoE: 设施硬约束二次确认（AND 语义，排除不满足硬要求的房源）"
    tools: list[str] = []  # 不需要工具，纯计算

    async def handle(self, context: AgentContext) -> AgentResult:
        """执行硬约束检查。

        从 context 中读取：
        - context.filters: 包含 amenities/room_type/bathrooms 等硬约束
        - context.search_state: 包含 search_agent 的候选结果
        - context.extra: 可能包含上游 Agent 的结构化输出
        """
        filters: dict[str, Any] = context.filters or {}
        required_amenities: list[str] = filters.get("amenities") or []
        required_room_type: str | None = filters.get("room_type")
        required_bathrooms: int | None = filters.get("bathrooms")

        # 如果没有硬约束，直接返回空结果（表示无需过滤）
        if not required_amenities and not required_room_type and not required_bathrooms:
            return AgentResult(
                content=json.dumps({"passed": [], "excluded": [], "total": 0,
                                    "note": "无硬约束，跳过设施检查"}, ensure_ascii=False),
                success=True,
                data={"no_hard_constraints": True},
            )

        # 尝试从 context.extra 和 context.search_state 获取候选房源
        candidates: list[dict[str, Any]] = []

        # 路径 1：context.extra 中有 search_agent 的结构化结果
        if context.extra:
            raw = context.extra.get("search_results") or context.extra.get("candidates") or []
            if raw:
                candidates = raw

        # 路径 2：context.search_state 中可能有搜索结果
        if not candidates and context.search_state:
            if hasattr(context.search_state, "last_search_results"):
                raw = context.search_state.last_search_results or []
                candidates = [{"property": r[0]} if isinstance(r, tuple) else r for r in raw]

        # 路径 3：从 filters 元数据中获取
        if not candidates:
            hard_filter_dims = filters.get("_hard_constraint_dims") or []
            if not hard_filter_dims:
                return AgentResult(
                    content=json.dumps({"passed": [], "excluded": [], "total": 0,
                                        "note": "无法获取候选房源列表，但检测到硬约束", "required": required_amenities},
                                       ensure_ascii=False),
                    success=True,
                    data={"no_candidates": True, "required": required_amenities},
                )

        result = check_hard_constraints(
            candidates=candidates,
            required_amenities=required_amenities,
            required_room_type=required_room_type,
            required_bathrooms=required_bathrooms,
        )

        return AgentResult(
            content=json.dumps({
                "passed_count": result["passed_count"],
                "excluded_count": result["excluded_count"],
                "total": result["total"],
                "required": required_amenities,
                "excluded_reasons": [
                    {"property_id": c.get("property", {}).id if hasattr(c.get("property", {}), "id") else None,
                     "missing": c.get("_missing_amenities", [])}
                    for c in result["excluded"][:10]  # 最多 10 条排除原因
                ],
            }, ensure_ascii=False),
            success=True,
            data=result,
        )

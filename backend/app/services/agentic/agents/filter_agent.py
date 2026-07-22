"""筛选 Agent —— LLM 只提取偏好操作，状态合并由确定性服务完成。"""
from __future__ import annotations

import json
import logging

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult
from app.services.preference_state import (
    apply_explicit_filters,
    apply_preference_operations,
    flatten_preference_state,
    normalize_preference_state,
)

logger = logging.getLogger(__name__)

# 设施词汇映射：用户口语 → 数据库标准值
_AMENITY_ALIASES: dict[str, list[str]] = {
    "宠物友好": ["养宠物", "养猫", "养狗", "可养宠物", "能养猫", "能养狗", "宠物", "猫", "狗"],
    "独立厨房": ["厨房", "独立厨房", "开放厨房", "可做饭", "能做饭", "有厨房"],
    "独立卫浴": ["独卫", "独立卫生间", "独立卫浴", "单独卫生间", "私人卫生间"],
    "空调": ["空调", "冷气", "制冷"],
    "洗衣机": ["洗衣机", "洗衣", "烘干机"],
    "冰箱": ["冰箱", "冰柜"],
    "WiFi": ["wifi", "WiFi", "无线网", "宽带", "网络", "上网"],
    "暖气": ["暖气", "地暖", "供暖", "取暖"],
    "阳台": ["阳台", "露台"],
    "电梯": ["电梯", "有电梯"],
    "车位": ["车位", "停车位", "停车场", "停车"],
    "健身房": ["健身房", "健身", "gym"],
    "泳池": ["泳池", "游泳池", "游泳"],
    "自习室": ["自习室", "自习", "学习室"],
    "家具齐全": ["家具", "拎包", "家具齐全", "拎包入住"],
    "精装修": ["精装", "精装修", "装修好"],
    "包水电": ["包水电", "包水电网", "全包"],
    "禁烟": ["禁烟", "无烟", "不吸烟", "禁止吸烟"],
}


def _normalize_amenities(raw: list[str]) -> list[str]:
    """将用户口语化的设施描述映射为数据库标准值。"""
    if not raw:
        return []
    normalized: list[str] = []
    for item in raw:
        matched = False
        for standard, aliases in _AMENITY_ALIASES.items():
            if item in aliases or item == standard:
                if standard not in normalized:
                    normalized.append(standard)
                matched = True
                break
        if not matched:
            normalized.append(item)
    return normalized


class FilterAgent(BaseAgent):
    name = "filter_agent"
    description = "从自然语言提取结构化筛选条件（含硬约束设施/房型/周边/通勤）"
    tools = ["extract_filters", "query_rewrite"]

    FILTER_PROMPT = """你是租房偏好操作提取器。只判断用户本轮要对偏好状态做哪些操作，不负责合并最终状态。

══════════════════════════════
当前偏好状态
══════════════════════════════
{PREV_FILTERS_PLACEHOLDER}

只输出 JSON：
{"operations":[{"op":"set|update|add|remove|clear","field":"字段名","value":任意值,"strength":"hard|soft","weight":0.0到1.0}]}

允许字段：country, district, price_min, price_max, bedrooms, property_type,
amenities, room_type, bathrooms, area_min, area_max, min_lease_months,
max_lease_months, available_from, institution, distance_km, commute_mode,
commute_minutes, poi_requirements。

操作规则：
- set/update：设置或修改标量；update 也可按 POI type 更新距离。
- add：给 amenities 或 poi_requirements 追加一项，不返回整份旧列表。
- remove：只移除用户点名的标量或列表项。
- clear：用户说“重新搜/清空条件”时输出 {"op":"clear"}，不要附 field。
- 用户没有修改的旧条件不要输出，后端会自动保留。

强度规则：
- “必须/一定/没有就不考虑/预算内/不超过/以内”是 hard。
- “最好/尽量/有的话/也行/优先”是 soft，weight 默认 0.6。
- 明确的总预算上限默认 hard；普通配套（超市、健身房、医疗）默认 soft。
- 用户明确说配套“必须在 X 米内”时才是 hard。

设施映射（value 输出标准值）：
   "养猫"/"养狗" → "宠物友好"
   "做饭"/"厨房" → "独立厨房"
   "独卫"/"独立卫生间" → "独立卫浴"
   "wifi"/"宽带" → "WiFi"
   "车位"/"停车" → "车位"
   "gym"/"健身" → "健身房"
   "泳池"/"游泳" → "泳池"
   "家具"/"拎包入住" → "家具齐全"
   "精装"/"装修好" → "精装修"
   "禁烟"/"无烟" → "禁烟"

POI value 格式：{"type":"supermarket|gym|medical|transit","target_m":500,"acceptable_m":1200}。

示例：
- “预算不超过3500” → {"operations":[{"op":"set","field":"price_max","value":3500,"strength":"hard"}]}
- “最好500米内有超市” → {"operations":[{"op":"add","field":"poi_requirements","value":{"type":"supermarket","target_m":500,"acceptable_m":1200},"strength":"soft","weight":0.6}]}
- “健身房不重要了” → {"operations":[{"op":"remove","field":"poi_requirements","value":{"type":"gym"}}]}
- “还要阳台” → {"operations":[{"op":"add","field":"amenities","value":"阳台","strength":"soft","weight":0.6}]}
- “预算提高到4000” → {"operations":[{"op":"update","field":"price_max","value":4000,"strength":"hard"}]}
- “重新搜” → {"operations":[{"op":"clear"}]}

不要输出解释、markdown 或最终合并状态。"""


    async def handle(
        self, context: AgentContext, prev_filters: dict | None = None,
    ) -> AgentResult:
        """从用户消息提取结构化筛选条件。

        Args:
            context: Agent 上下文（含 user_message）
            prev_filters: 上轮结构化偏好状态，由 reducer 确定性合并
        """
        state = normalize_preference_state(prev_filters)
        explicit_filters = context.filters if isinstance(context.filters, dict) else {}
        if state["filters"]:
            prev_json = json.dumps(state["filters"], ensure_ascii=False, indent=2)
        else:
            prev_json = "null（首轮对话，无上轮条件）"
        prompt = self.FILTER_PROMPT.replace("{PREV_FILTERS_PLACEHOLDER}", prev_json)

        operations: list[dict] = []
        if self.llm_service.is_available:
            try:
                result = await self.llm_service.complete_json(
                    prompt, context.user_message,
                    temperature=0.0, max_tokens=500,
                )
                if isinstance(result, dict) and isinstance(result.get("operations"), list):
                    operations = [op for op in result["operations"] if isinstance(op, dict)]
            except Exception:
                logger.exception("filter_agent LLM 操作提取失败，保留现有偏好")

        # 设施别名标准化只影响本轮操作；最终合并由 reducer 确定性执行。
        for operation in operations:
            if operation.get("field") != "amenities" or operation.get("value") is None:
                continue
            raw = operation["value"] if isinstance(operation["value"], list) else [operation["value"]]
            normalized = _normalize_amenities(raw)
            operation["value"] = normalized if isinstance(operation["value"], list) else (normalized[0] if normalized else None)

        state = apply_preference_operations(state, operations)
        state = apply_explicit_filters(state, explicit_filters)
        payload = flatten_preference_state(state)
        return AgentResult(
            content="",
            success=True,
            data=payload,
            context_updates={"filters": payload, "preference_state": state},
        )

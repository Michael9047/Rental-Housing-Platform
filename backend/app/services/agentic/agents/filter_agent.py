"""筛选 Agent —— NL → 结构化筛选条件（含硬约束）。"""
from __future__ import annotations

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult

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

    FILTER_PROMPT = """你是租房搜索条件提取助手。从用户消息中提取结构化条件，区分硬约束（必须满足，排除不满足的房源）和软偏好（排序优先级）。

只输出 JSON：
{
  "district": "城市或区域名，null=未提及",
  "price_min": 最低月租整数，null=未提及,
  "price_max": 最高月租整数，null=未提及,
  "bedrooms": 卧室数整数，null=未提及,
  "property_type": "apartment/house/studio/shared 或 null",
  "amenities": ["设施1", "设施2"],
  "room_type": "studio/ensuite/1bed/2bed/3bed+/shared 或 null",
  "bathrooms": 卫生间数整数，null=未提及,
  "area_min": 最小面积(㎡)整数，null=未提及,
  "area_max": 最大面积(㎡)整数，null=未提及,
  "min_lease_months": 最短租期(月)整数，null=未提及,
  "institution": "大学/学校/机构名，null=未提及",
  "commute_mode": "walking/bicycling/driving/transit 或 null",
  "commute_minutes": 通勤时间上限整数(分钟)，null=未提及,
  "hard_filters": ["标记为硬约束的字段名列表"],
  "soft_preferences": ["标记为软偏好的字段名列表"]
}

关键规则：
1. amenities 提取用户明确要求的具体设施，使用以下标准值：
   宠物友好、独立厨房、独立卫浴、空调、洗衣机、冰箱、WiFi、暖气、阳台、电梯、车位、健身房、泳池、自习室、家具齐全、精装修、包水电、禁烟
   - "能养猫"/"可以养狗" → amenities: ["宠物友好"]
   - "可以做饭"/"有厨房" → amenities: ["独立厨房"]
   - "独立卫生间"/"独卫" → amenities: ["独立卫浴"]
   - "有wifi"/"能上网" → amenities: ["WiFi"]
   - "能抽烟" → 不要加入 amenities（用户需要可吸烟，不要求禁烟）

2. hard_filters vs soft_preferences 判断标准：
   - 硬约束（排除性）：amenities、room_type、bathrooms、commute（用户说"必须有""一定要""没有就不考虑"）
   - 软偏好（排序性）：price、district、area、bedrooms（用户说"最好""尽量""便宜点就行"）
   - 未明确标注时：amenities/room_type/commute 默认硬约束，price/district/area 默认软偏好

3. 设施口语映射（不要直接输出用户原词，映射到标准值）：
   - "养猫"/"养狗"/"宠物" → "宠物友好"
   - "做饭"/"厨房" → "独立厨房"
   - "独卫"/"独立卫生间" → "独立卫浴"
   - "wifi"/"宽带"/"网络" → "WiFi"
   - "车位"/"停车" → "车位"
   - "gym"/"健身" → "健身房"
   - "泳池"/"游泳" → "泳池"
   - "家具"/"拎包入住" → "家具齐全"

4. 英文城市名转中文（London→伦敦, Hong Kong→香港等）
5. 不确定时填 null，只输出 JSON"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="{}", success=True, data={})

        try:
            result = await self.llm_service.complete_json(
                self.FILTER_PROMPT, context.user_message,
                temperature=0.0, max_tokens=500,
            )
            if not isinstance(result, dict):
                return AgentResult(content="{}", success=True, data={})

            # 标准化 amenities 值
            raw_amenities: list[str] = result.get("amenities") or []
            if raw_amenities:
                result["amenities"] = _normalize_amenities(raw_amenities)

            return AgentResult(
                content=str(result),
                success=True,
                data=result,
            )
        except Exception:
            return AgentResult(content="{}", success=True, data={})

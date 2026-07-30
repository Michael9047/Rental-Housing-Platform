"""筛选 Agent —— NL → 结构化筛选条件（含硬约束）。

支持跨轮上下文记忆：接收上轮 accumulated_filters，由 LLM 判断合并/修改/重置。
"""
from __future__ import annotations

import json
import logging

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult

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

    FILTER_PROMPT = """你是租房搜索条件提取助手。从用户消息中提取结构化条件，区分硬约束和软偏好。

══════════════════════════════
示例（Few-Shot）
══════════════════════════════

示例1：
用户：「园区2000以内一定要独卫的单间」
→ {"district":"园区","price_max":2000,"amenities":["独立卫浴"],"property_type":"studio","price_min":null,"bedrooms":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null,"institution":null,"commute_mode":null,"commute_minutes":null,"hard_filters":["amenities","district"],"soft_preferences":["price"]}

示例2：
用户：「文星附近能养猫的房子，最好1500左右，合租也行」
→ {"district":"文星","price_min":1350,"price_max":1650,"amenities":["宠物友好"],"property_type":"shared","bedrooms":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null,"institution":null,"commute_mode":null,"commute_minutes":null,"hard_filters":["amenities"],"soft_preferences":["price","district","property_type"]}

示例3：
用户：「学校步行15分钟内，2500预算，要带阳台和独卫，精装修最好」
→ {"district":null,"price_max":2500,"amenities":["独立卫浴","阳台"],"property_type":null,"bedrooms":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null,"institution":"悉尼大学","commute_mode":"walking","commute_minutes":15,"hard_filters":["amenities","commute"],"soft_preferences":["price","精装修"]}

══════════════════════════════
只输出 JSON
══════════════════════════════
{
  "district": "区域名，null=未提及",
  "price_min": 最低月租整数，null=未提及,
  "price_max": 最高月租整数，null=未提及,
  "bedrooms": 卧室数整数，null=未提及,
  "property_type": "studio/1-bed/2-bed/shared/house 或 null",
  "amenities": ["标准设施名"],
  "room_type": "studio/ensuite/1bed/2bed/3bed+/shared 或 null",
  "bathrooms": 卫生间数整数，null=未提及,
  "area_min": 最小面积(㎡)，null=未提及,
  "area_max": 最大面积(㎡)，null=未提及,
  "min_lease_months": 最短租期(月)，null=未提及,
  "institution": "学校名，null=未提及",
  "commute_mode": "walking/bicycling/driving/transit 或 null",
  "commute_minutes": 通勤时间上限(分钟)，null=未提及,
  "hard_filters": ["硬约束字段名"],
  "soft_preferences": ["软偏好字段名"]
}

══════════════════════════════
关键规则
══════════════════════════════

1. 硬约束 vs 软偏好：
   - 硬约束：用户说"必须""一定要""没有就不考虑" → amenities, room_type, bathrooms, commute
   - 软偏好：用户说"最好""尽量""便宜点就行""XX也行" → price, district, area, bedrooms
   - 默认：amenities/room_type/commute=硬约束, price/district/area=软偏好

2. 设施映射（输出标准值，不要用用户原词）：
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

3. "1500左右" → price_min=1350, price_max=1650（±10%）
4. 英文城市名转中文
5. 不确定时填 null

══════════════════════════════
上下文合并规则（上轮条件存在时适用）
══════════════════════════════
上轮已提取的筛选条件（JSON）：
{PREV_FILTERS_PLACEHOLDER}

示例4（增量修改）：
上轮：{"institution":"悉尼大学","price_max":20000,"amenities":["健身房"],...}
用户：「那健身房不带也就算了」
→ 合并："institution":"悉尼大学","price_max":20000 — 保留；"amenities":[] — 移除健身房。只去掉这一项，其余不动。

示例5（数值修改）：
上轮：{"institution":"悉尼大学","price_max":20000,...}
用户：「预算提到25000吧」
→ 合并："price_max":25000 — 更新；其余全部保留。

示例6（追加条件）：
上轮：{"institution":"悉尼大学","price_max":20000,...}
用户：「还要阳台」
→ 合并："amenities":["阳台"] — 在上轮基础上追加。

用户可能在当前消息中对上轮条件做增量修改。合并策略：
- 用户说"那XX不带也就算了""算了不要XX了""XX去掉吧" → 移除该条件，其余全部保留
- 用户说"XX也加上""还要XX""顺便看看有没有XX" → 在上轮基础上追加该条件
- 用户说"预算提到X""价格改到X以内" → 仅更新 price 字段，其余保留
- 用户说"换成XX附近""还是XX学校吧" → 仅更新 district/institution，其余保留
- 用户说"重新搜""从零开始""清掉之前的条件" → 丢弃上轮全部条件，只从当前消息提取
- 用户消息没有引用/修改上轮条件 → 保留上轮条件，仅从当前消息补充新条件
- 上轮为 null → 忽略本节，当前消息独立提取"""


    async def handle(
        self, context: AgentContext, prev_filters: dict | None = None,
    ) -> AgentResult:
        """从用户消息提取结构化筛选条件。

        Args:
            context: Agent 上下文（含 user_message）
            prev_filters: 上轮累积的筛选条件，由 LLM 判断合并/修改/重置
        """
        if not self.llm_service.is_available:
            return AgentResult(content="{}", success=True, data={})

        # 构建 prompt：注入上轮条件（如果有）
        if prev_filters and isinstance(prev_filters, dict) and len(prev_filters) > 0:
            prev_json = json.dumps(prev_filters, ensure_ascii=False, indent=2)
        else:
            prev_json = "null（首轮对话，无上轮条件）"
        prompt = self.FILTER_PROMPT.replace("{PREV_FILTERS_PLACEHOLDER}", prev_json)

        try:
            result = await self.llm_service.complete_json(
                prompt, context.user_message,
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
            logger.exception("filter_agent LLM 提取失败")
            return AgentResult(content="{}", success=True, data={})

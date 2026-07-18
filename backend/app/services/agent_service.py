"""租房推荐 Agent 服务 —— 意图解析、房源推荐、购物车管理、房源对比

v2: 漏斗型对话 Agent —— 多轮收敛、检索放宽、查询改写、安全兜底、一致性校验。

复用 PropertyService.search 做检索，复用 chat_sessions/chat_messages 存对话，
LLM 仅基于数据库中的真实房源数据生成推荐理由和对比分析；
LLM 不可用时降级为普通筛选 + 规则化对比。
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_cart import AgentCart, AgentCartItem
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.models.poi import PropertyPOI
from app.models.property import Property, PropertyStatus
from app.models.review import Review, ReviewStatus
from app.services.agent_faq import FaqEntry, get_faq, match_faq
from app.services.compare_scoring import (
    DIMENSION_LABELS,
    PRIORITY_LABELS,
    PropertyMetrics,
    compute_scores,
    format_commute,
    nearest_transit_meters,
    normalize_priority,
)
from app.services.llm_service import get_llm_service
from app.services.property_service import PropertyService
from app.services.safe_fallback import SafeFallback
from app.services.score_gap import detect_score_gap

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_HINT = "（AI 分析暂不可用，已按筛选条件为您检索）"

# ── 检索放宽配置 ──────────────────────────────────────────────────
RELAXATION_MIN_RESULTS = 5
RELAXATION_ORDER: list[dict] = [
    {"key": "district", "label": "区域"},
    {"key": "property_type", "label": "房源类型"},
    {"key": "bedrooms", "label": "户型"},
    {"key": "price_max", "label": "预算上限", "expand_factor": 1.2},
]

# ── 意图解析提示词 ─────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """你是租房平台的智能助手。判断用户这句话的意图，只输出 JSON：

{
  "intent": "recommend | add_to_cart | remove_from_cart | compare_cart | faq | general 之一",
  "refs": [用户提到的序号列表，如"第一个"是 1，"前两个"是 1 和 2，没提到则为空数组],
  "faq_id": "仅当 intent 为 faq 时给出：find_house | booking | contract | deposit | refund | fees 之一",
  "faq_confidence": "仅当 intent 为 faq 时给出：high 或 low"
}

意图说明：
- recommend：用户在描述租房需求，希望推荐房源
- add_to_cart：用户想把某个/某些房源加入购物车或候选清单
- remove_from_cart：用户想从购物车/清单移除房源
- compare_cart：用户想对比购物车/清单中的房源
- faq：用户在问平台使用/政策类问题（find_house 如何找房 / booking 预订流程 /
  contract 合同签署 / deposit 押金退还 / refund 退款政策 / fees 费用构成）。
  很确定属于其中一类填 high；只是可能相关、拿不准填 low。
- general：与上述都无关的普通咨询

只输出 JSON。"""

# ── 统一意图 + 阶段 + 路由分类提示词 ───────────────────────────
UNIFIED_CLASSIFIER_PROMPT = """你是租房平台的智能对话路由器。分析用户消息，一次输出完整的分类结果。

只输出 JSON（不要 markdown 包裹）：
{
  "intent": "search | manage_cart | compare | faq | general",
  "sub_intent": "见下方各 intent 的 sub_intent 取值",
  "stage": "explore | calibrate | narrow | compare | decide | general",
  "complexity": 0.0-1.0,
  "confidence": 0.0-1.0,
  "routing": "fast | agent",
  "faq_topic": null,
  "faq_confidence": null,
  "refs": [],
  "reasoning": "简短理由，≤20 字"
}

【search】— 用户在表达找房需求
  sub_intent: "explore" | "browse" | "filter" | "detail" | "commute"
【manage_cart】— 购物车/候选清单操作
  sub_intent: "add" | "remove" | "view"
【compare】— 对比房源
  sub_intent: "cart" | "specific"
【faq】— 平台使用/政策/流程问题
  sub_intent: "how_to_find" | "booking" | "contract" | "deposit" | "refund" | "fees" | "other"
【general】— 闲聊、问候
  sub_intent: "chitchat" | "greeting" | "other"

routing:
  "fast"  — 直接回复（FAQ、简单闲聊）
  "agent" — 进入 Agent 管道（搜索推荐、对比分析、多步推理）

只输出 JSON。"""

RECOMMEND_SYSTEM_PROMPT = """你是西交利物浦大学周边的租房推荐助手。系统已经从数据库检索出候选房源（附真实数据）。你的任务是从中挑选最匹配的 3 套精选房源，用口语化的中文撰写推荐回复。

回复结构（三段式，自然口语化）：

1. <开头一句话> 总结匹配情况，用口语化语气。例：
   「帮你筛了一下，园区预算 2000 以内的单间有 X 套，这 3 套最值得看：」
   「附近 1500 以下的房源不多，但这几套性价比不错：」

2. <逐套介绍> 每套 1-2 句话，格式：
   「<亮点标签> — <小区/位置>，<户型> ¥<价格>/月，<核心卖点，逗号分隔>」
   例：「通勤首选 — 翰林缘，单间 ¥1800/月，步行到校 10 分钟，独卫精装，家具齐全」

3. <收尾引导> 一句话引导下一步动作。例：
   「可以横滑看卡片对比，有中意的就加购物车，我帮你详细对比。」

严格规则：
1. 只推荐候选列表里的 property_id，禁止编造房源、价格、地址、设施。
2. 基于真实字段撰写（价格、区域、户型、面积、描述、通勤、设施），不要凭空发挥。
3. 价格用"¥"符号，不要用"元"或"块"。
4. 候选为空时，recommendations 返回空数组，reply 建议用户放宽条件（如扩大区域、提高预算、去掉设施限制）。
5. 精选最多 3 套，按匹配度降序排列。
6. 回复控制在 200 字以内，精炼不啰嗦。

只输出 JSON，格式：
{
  "intent": "recommend",
  "reply": "口语化推荐回复（三段式）",
  "recommendations": [
    {
      "property_id": 1,
      "match_reason": "通勤便利，性价比高",
      "pros": ["步行 10 分钟到校", "精装独卫"],
      "cons": ["面积偏小"]
    }
  ]
}"""

COMPARE_SYSTEM_PROMPT = """你是租房平台的智能对比助手。系统已经按用户选择的优先级，用数据库真实数据（价格、面积、最近交通站点距离、机构真实评价）计算好每套房源的综合得分和分项得分。你的任务是**解释和分析**，不是打分。

严格规则：
1. 只能基于给出的真实字段分析，禁止编造价格、距离、设施、评价。
2. items 必须覆盖给出的每一套房源，property_id 不得超出给定列表。
3. score 必须原样使用系统计算的综合得分，禁止修改或自创。
4. pros/cons 结合价格、通勤（最近交通站点距离）、面积、评价与描述来写，和分项得分保持一致。
5. recommendation 要呼应用户的优先级（如预算优先/通勤优先）。

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

GENERAL_SYSTEM_PROMPT = """你是一个专业的租房顾问助手，用中文简洁友好地回答用户的租房相关咨询。
不要编造任何不存在的房源信息；如果用户想找房，引导他描述地区、预算、户型等需求。"""

# ── 从用户消息中提取结构化搜索条件 ────────────────────────
EXTRACT_FILTERS_PROMPT = """从用户消息中提取结构化的租房搜索条件。只输出 JSON：

{
  "district": "城市或区域名称。无法确定则为 null",
  "price_min": 最低月租金整数，未提及则为 null,
  "price_max": 最高月租金整数，未提及则为 null,
  "bedrooms": 卧室数量整数，未提及则为 null,
  "property_type": "apartment/house/studio/shared 之一，未提及则为 null",
  "institution": "大学/学校/机构名称。无法确定则为 null",
  "distance_km": 距学校的搜索半径（公里），默认 3.0。仅在 commute_mode 为 null 时填入精确值",
  "commute_mode": "walking/bicycling/driving/transit 之一，未提及通勤方式则为 null",
  "commute_minutes": 通勤时间上限（分钟），未提及则为 null,
  "amenities": ["设施标准值列表"],
  "room_type": "studio/ensuite/1bed/2bed/3bed+/shared 或 null",
  "bathrooms": 卫生间数整数，null=未提及,
  "area_min": 最小面积(㎡)整数，null=未提及,
  "area_max": 最大面积(㎡)整数，null=未提及,
  "min_lease_months": 最短租期(月)整数，null=未提及
}

关键规则：
- district 是行政区划名称，不要把学校名填进去
- "NUS附近" → district=null, institution="NUS"
- "新加坡国立大学附近" → district=null, institution="NUS"
- 不确定时填 null，只输出 JSON

设施提取规则（amenities 使用以下标准值）：
- "能养猫"/"可以养狗"/"宠物" → ["宠物友好"]
- "可以做饭"/"有厨房" → ["独立厨房"]
- "独卫"/"独立卫生间" → ["独立卫浴"]
- "有wifi"/"能上网" → ["WiFi"]
- "有空调" → ["空调"]
- "有洗衣机" → ["洗衣机"]
- "有冰箱" → ["冰箱"]
- "有阳台" → ["阳台"]
- "有电梯" → ["电梯"]
- "有车位"/"能停车" → ["车位"]
- "有健身房"/"gym" → ["健身房"]
- "有泳池" → ["泳池"]
- "家具齐全"/"拎包入住" → ["家具齐全"]
- "禁烟"/"无烟" → ["禁烟"]
- 未提及设施 → amenities: []

通勤模式推断规则（仅当用户明确提出通勤时间要求时填写）：
- "步行30分钟内" → commute_mode="walking", commute_minutes=30, distance_km=5.0
- "骑车15分钟" → commute_mode="bicycling", commute_minutes=15, distance_km=10.0
- "开车10分钟" → commute_mode="driving", commute_minutes=10, distance_km=20.0
- "公交20分钟"、"地铁半小时" → commute_mode="transit", commute_minutes=20 或 30, distance_km=15.0
- "步行距离" (未提具体分钟) → commute_mode="walking", commute_minutes=20, distance_km=5.0
- commute_mode 不为 null 时，distance_km 使用宽松值作为预筛选半径
- commute_mode 为 null 时，distance_km 按旧规则：未提及→3.0"""

# ── 通勤模式预筛选半径（km）— Haversine 宽松预筛选，确保不漏掉路线 API 可达的房源 ──
_COMMUTE_PRE_FILTER_KM: dict[str, float] = {
    "walking": 5.0,
    "bicycling": 10.0,
    "driving": 20.0,
    "transit": 15.0,
}
_COMMUTE_RELAX_MULTIPLIERS = (1, 2, 3, 4)

# ── 英文城市名 → 中文映射 ────────────────────
_EN_TO_CN_CITY: dict[str, str] = {
    "london": "伦敦", "hong kong": "香港", "hk": "香港",
    "singapore": "新加坡", "sg": "新加坡",
    "los angeles": "洛杉矶", "la": "洛杉矶",
    "san francisco": "旧金山", "sf": "旧金山",
}

# ── 中文序号解析 ──────────────────────────────────────────────────

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

_ADD_PATTERN = re.compile(r"(加入|加到|添加|放进|放入|收藏|加购)")
_REMOVE_PATTERN = re.compile(r"(移除|删除|去掉|拿掉|清除)")
_COMPARE_PATTERN = re.compile(r"(对比|比较|哪个好|哪套好|哪一?[个套]更)")
_CART_PATTERN = re.compile(r"(购物车|候选|清单|收藏)")
# 找房信号词：命中即直接走 recommend，跳过 LLM 意图分类（省一次串行调用，显著降低延迟）
_RECOMMEND_SIGNAL = re.compile(
    r"找|推荐|租|房源|房子|居室|单间|公寓|合租|别墅|预算|地铁|学校|大学|附近|[0-9一二两三四五]\s*室|元|块|㎡|平米|平方"
)


def _parse_refs(message: str) -> list[int]:
    """从消息中提取序号引用，如 '第一个'、'第2套' → [1] / [2]"""
    refs: list[int] = []
    for m in re.finditer(r"第\s*(\d+|[一二两三四五六七八九十])\s*[个套条]?", message):
        token = m.group(1)
        num = int(token) if token.isdigit() else _CN_NUM.get(token, 0)
        if num > 0:
            refs.append(num)
    if re.search(r"(前两[个套]|前2[个套])", message):
        refs.extend([1, 2])
    if re.search(r"(全部|都加|所有)", message):
        refs.append(-1)  # -1 表示全部
    return list(dict.fromkeys(refs))


def _parse_property_ids(message: str) -> list[int]:
    """提取显式房源 ID 引用，如 '房源 12'"""
    return [int(m.group(1)) for m in re.finditer(r"房源\s*(\d+)", message)]


def _heuristic_intent(message: str) -> str:
    """无需 LLM 的规则意图判断"""
    if _COMPARE_PATTERN.search(message):
        return "compare_cart"
    if _ADD_PATTERN.search(message) and (_CART_PATTERN.search(message) or _parse_refs(message) or _parse_property_ids(message)):
        return "add_to_cart"
    if _REMOVE_PATTERN.search(message) and (_CART_PATTERN.search(message) or _parse_refs(message) or _parse_property_ids(message)):
        return "remove_from_cart"
    return "recommend"


def _property_to_dict(prop: Property) -> dict[str, Any]:
    """将 Property ORM 转为 LLM 上下文用的 dict（仅真实字段）"""
    return {
        "property_id": prop.id,
        "title": prop.title,
        "district": prop.district,
        "address": prop.address,
        "price_monthly": float(prop.price_monthly),
        "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "property_type": prop.property_type.value if hasattr(prop.property_type, "value") else str(prop.property_type),
        "description": (prop.description or "")[:200],
    }


def _props_text(props: list[Property]) -> str:
    lines = []
    for i, p in enumerate(props, 1):
        d = _property_to_dict(p)
        line = (
            f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | 地址: {d['address']} | "
            f"月租: ¥{d['price_monthly']} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
            f"面积: {d['area_sqm'] or '未知'}㎡ | 类型: {d['property_type']} | 简介: {d['description'] or '无'}"
        )
        commute_time = getattr(p, '_commute_time', None)
        if commute_time is not None:
            source_note = "（路线API实时计算）" if getattr(p, '_commute_source', None) == "api" else "（估算）"
            line += f" | 通勤: {commute_time}分钟{source_note}"
        lines.append(line)
    return "\n".join(lines)


def _build_dimension_analysis(
    props: list[Property],
    scores: dict[int, dict],
    extras: dict[int, dict],
    priority: str,
    llm_result: dict[str, Any] | None = None,
) -> str:
    """用真实数据构建按维度组织的对比分析 Markdown（非 LLM，确定性输出）。

    维度顺序：通勤 → 周边配套 → 房内设施 → 价格 → 空间 → 评价与安全 → 综合推荐
    """
    by_id = {p.id: p for p in props}
    lines: list[str] = []

    # ── 标题 ──
    summary = (llm_result or {}).get("summary", "") if llm_result else ""
    if summary:
        lines.append(f"> {summary}\n")

    lines.append("## 📊 多维度对比分析\n")

    # ── 1. 通勤交通 ──
    lines.append("### 🚇 通勤交通")
    sorted_commute = sorted(props, key=lambda p: (
        float("inf") if extras[p.id].get("commute") is None
        else _parse_commute_meters(extras[p.id].get("commute", ""))
    ))
    for p in sorted_commute:
        c = extras[p.id].get("commute") or "暂无数据"
        s = scores[p.id]["breakdown"].get("commute", 0)
        lines.append(f"- **{p.title}**：{c}（通勤得分 {s}）")
    # 标注最优
    if sorted_commute:
        best = sorted_commute[0]
        if extras[best.id].get("commute"):
            lines.append(f"\n✅ 通勤最优：**{best.title}**\n")

    # ── 2. 周边配套（从描述和区域推断） ──
    lines.append("### 🏪 周边配套")
    for p in props:
        d = _property_to_dict(p)
        district_info = d.get("district", "未知区域")
        desc = (d.get("description") or "")[:120]
        # 从描述中提取设施关键词
        facility_hints = _extract_facility_hints(desc)
        hint_text = f"（{'、'.join(facility_hints)}）" if facility_hints else ""
        lines.append(f"- **{p.title}**：位于{district_info}{hint_text}")
    lines.append("")

    # ── 3. 房内设施 ──
    lines.append("### 🛋️ 房内设施")
    for p in props:
        desc = (p.description or "")[:200]
        amenities = _extract_amenities_from_desc(desc)
        if amenities:
            lines.append(f"- **{p.title}**：{'、'.join(amenities)}")
        else:
            lines.append(f"- **{p.title}**：设施信息待补充（请联系房东确认）")
    lines.append("")

    # ── 4. 价格对比 ──
    lines.append("### 💰 价格对比")
    sorted_price = sorted(props, key=lambda p: float(p.price_monthly))
    for p in sorted_price:
        s = scores[p.id]["breakdown"].get("price", 0)
        deposit = getattr(p, "deposit_amount", None)
        deposit_text = f"（押金 ¥{float(deposit):.0f}）" if deposit else ""
        lines.append(f"- **{p.title}**：¥{float(p.price_monthly):.0f}/月 {deposit_text}（价格得分 {s}）")
    lines.append(f"\n💰 价格最低：**{sorted_price[0].title}**（¥{float(sorted_price[0].price_monthly):.0f}/月）\n")

    # ── 5. 空间户型 ──
    lines.append("### 📐 空间户型")
    sorted_space = sorted(props, key=lambda p: float(p.area_sqm or 0), reverse=True)
    for p in sorted_space:
        s = scores[p.id]["breakdown"].get("space", 0)
        area = f"{p.area_sqm}㎡" if p.area_sqm else "未知"
        lines.append(f"- **{p.title}**：{area}，{p.bedrooms}室{p.bathrooms}卫（空间得分 {s}）")
    lines.append(f"\n📐 空间最大：**{sorted_space[0].title}**\n")

    # ── 6. 评价与安全 ──
    lines.append("### ⭐ 评价与安全")
    for p in props:
        e = extras[p.id]
        if e.get("rating") is not None:
            lines.append(f"- **{p.title}**：★ {e['rating']:.1f}（{e['review_count']}条评价）")
        else:
            lines.append(f"- **{p.title}**：暂无评价数据")
    lines.append("")

    # ── 7. 综合排序与推荐 ──
    lines.append("### 🏆 综合排序")
    sorted_total = sorted(props, key=lambda p: scores[p.id]["total"], reverse=True)
    rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for rank, p in enumerate(sorted_total):
        emoji = rank_emoji[rank] if rank < len(rank_emoji) else f"{rank+1}."
        total = scores[p.id]["total"]
        bd = scores[p.id]["breakdown"]
        dim_parts = [f"{DIMENSION_LABELS.get(k, k)} {v}" for k, v in bd.items()]
        lines.append(f"{emoji} **{p.title}** — {total} 分（{' | '.join(dim_parts)}）")

    # LLM 推荐语
    recommendation = (llm_result or {}).get("recommendation", "") if llm_result else ""
    if recommendation:
        lines.append(f"\n💡 {recommendation}")

    return "\n".join(lines)


def _parse_commute_meters(commute_text: str) -> float:
    """从通勤文本中提取米数，用于排序。"""
    import re
    m = re.search(r"(\d+)\s*[m米]", commute_text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+\.?\d*)\s*[kK][mM]", commute_text)
    if m:
        return float(m.group(1)) * 1000
    return 10000  # 无数据排最后


def _extract_facility_hints(description: str) -> list[str]:
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
    return hints[:5]  # 最多5个


def _extract_amenities_from_desc(description: str) -> list[str]:
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


# ── 房源质量评分（确定性算法） ──────────────────────────

def _score_properties(
    candidates: list[Property],
    filters: dict[str, Any],
    extracted: dict[str, Any],
) -> list[dict[str, Any]]:
    """对候选房源进行确定性质量评分，返回 top 3 附带亮点理由。"""
    if not candidates:
        return []

    price_min = filters.get("price_min") or extracted.get("price_min")
    price_max = filters.get("price_max") or extracted.get("price_max")

    prices = [float(p.price_monthly) for p in candidates]
    median_price = sorted(prices)[len(prices) // 2]

    target_price = median_price
    if price_min is not None and price_max is not None:
        target_price = (float(price_min) + float(price_max)) / 2
    elif price_min is not None:
        target_price = float(price_min) * 1.1
    elif price_max is not None:
        target_price = float(price_max) * 0.9

    price_range = max(prices) - min(prices) if len(prices) > 1 else max(prices) or 1

    scored: list[dict[str, Any]] = []
    for p in candidates:
        price_diff = abs(float(p.price_monthly) - target_price)
        price_score = max(0, 100 - (price_diff / max(price_range, 1)) * 100)
        area = float(p.area_sqm) if p.area_sqm else 0
        space_score = min(100, (min(area / max((p.bedrooms or 0) * 20 + 15, 1), 2.0)) * 60 + 20) if area > 0 else 60
        facility_score = 60
        if p.images and len(p.images) > 0:
            facility_score += 15
        if p.address:
            facility_score += 10
        if p.description and len(p.description) > 20:
            facility_score += 10
        facility_score = min(100, facility_score)
        total = price_score * 0.40 + space_score * 0.20 + facility_score * 0.20 + 60 * 0.20

        highlights: list[str] = []
        if price_score >= 80:
            highlights.append("租金贴合预算")
        elif price_score >= 60:
            highlights.append("价格在可接受范围")
        if area > 0 and space_score >= 75:
            highlights.append(f"{p.bedrooms or 0}室{p.bathrooms or 0}卫布局合理")
        if p.images and len(p.images) > 0:
            highlights.append("有实拍图片")
        if p.district:
            highlights.append(f"位于{p.district}")
        if not highlights:
            highlights.append("符合筛选条件")

        scored.append({"property": p, "score": round(total, 1), "highlights": highlights[:3]})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.property_service = PropertyService(session)
        self._safe_fallback = SafeFallback()

    # ── 统一分类（v2：意图 + 阶段 + 路由，一次 LLM 调用）────────

    _VALID_INTENTS = frozenset({"search", "manage_cart", "compare", "faq", "general"})
    _VALID_STAGES = frozenset({"explore", "calibrate", "narrow", "compare", "decide", "general"})
    _VALID_ROUTING = frozenset({"fast", "agent"})

    async def classify_message(
        self, message: str, history: list[dict] | None = None
    ) -> dict[str, Any]:
        """统一分类：意图 + 阶段 + 路由信号，一次 LLM 调用完成。"""
        llm = get_llm_service()
        if not llm.is_available:
            return self._fallback_classify(message)

        history_text = ""
        if history:
            recent = history[-6:] if len(history) > 6 else history
            for msg in recent:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = str(msg.get("content", ""))[:200]
                history_text += f"{role}: {content}\n"

        user_prompt = f"对话历史：\n{history_text}\n用户最新消息: {message}" if history_text else message

        try:
            result = await llm.complete_json(UNIFIED_CLASSIFIER_PROMPT, user_prompt, temperature=0.0, max_tokens=300)
            intent = result.get("intent", "general")
            if intent not in self._VALID_INTENTS:
                intent = "general"
            sub_intent = str(result.get("sub_intent", ""))
            stage = result.get("stage", "explore")
            if stage not in self._VALID_STAGES:
                stage = "explore"
            complexity = max(0.0, min(1.0, float(result.get("complexity", 0.3))))
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            routing = result.get("routing", "fast")
            if routing not in self._VALID_ROUTING:
                routing = "agent" if complexity > 0.5 else "fast"
            faq_topic = result.get("faq_topic") if intent == "faq" else None
            faq_confidence = result.get("faq_confidence") if intent == "faq" else None
            refs = [r for r in result.get("refs", []) if isinstance(r, int)]
            refs = refs or _parse_refs(message)
            return {
                "intent": intent, "sub_intent": sub_intent, "stage": stage,
                "complexity": complexity, "confidence": confidence, "routing": routing,
                "faq_topic": faq_topic, "faq_confidence": faq_confidence,
                "refs": refs, "reasoning": str(result.get("reasoning", "")), "used_llm": True,
            }
        except Exception:
            logger.warning("统一分类 LLM 调用失败，降级为规则判断", exc_info=True)
            return self._fallback_classify(message)

    def _fallback_classify(self, message: str) -> dict[str, Any]:
        """规则兜底分类（LLM 不可用时）"""
        text = message.strip()
        result: dict[str, Any] = {
            "intent": "general", "sub_intent": "", "stage": "explore",
            "complexity": 0.2, "confidence": 0.5, "routing": "fast",
            "faq_topic": None, "faq_confidence": None,
            "refs": _parse_refs(message), "reasoning": "", "used_llm": False,
        }
        if _COMPARE_PATTERN.search(text):
            result.update({"intent": "compare", "sub_intent": "cart", "stage": "compare", "complexity": 0.6, "routing": "agent", "reasoning": "规则：对比信号"})
        elif _ADD_PATTERN.search(text) and (_CART_PATTERN.search(text) or result["refs"]):
            result.update({"intent": "manage_cart", "sub_intent": "add", "complexity": 0.2, "reasoning": "规则：加购信号"})
        elif _REMOVE_PATTERN.search(text):
            result.update({"intent": "manage_cart", "sub_intent": "remove", "complexity": 0.2, "reasoning": "规则：移除信号"})
        elif _RECOMMEND_SIGNAL.search(text):
            result.update({"intent": "search", "sub_intent": "browse", "complexity": 0.5, "routing": "agent", "reasoning": "规则：找房信号"})
        # 阶段判断
        if any(w in text for w in ["就这", "定了", "怎么看房", "约", "预订", "签约"]):
            result["stage"] = "decide"
        elif any(w in text for w in ["对比", "比较", "哪个好", "哪套好"]):
            result["stage"] = "compare"
        elif any(w in text for w in ["附近", "周边", "配套", "地铁", "公交", "距离", "多远"]):
            result["stage"] = "narrow"
        elif any(w in text for w in ["便宜", "贵", "少一点", "多一点", "以内", "不超过", "至少"]):
            result["stage"] = "calibrate"
        return result

    # ── 检索放宽 ──────────────────────────────────────────────────

    @staticmethod
    def _build_search_kwargs(filters: dict, limit: int = 500) -> dict[str, Any]:
        """将 Agent filters 转为 PropertyService.search() 的参数。"""
        kwargs: dict[str, Any] = {
            "price_min": Decimal(str(filters["price_min"])) if filters.get("price_min") is not None else None,
            "price_max": Decimal(str(filters["price_max"])) if filters.get("price_max") is not None else None,
            "bedrooms": filters.get("bedrooms"),
            "property_type": filters.get("property_type"),
            "status": PropertyStatus.available.value,
            "limit": limit,
        }
        district = filters.get("district")
        if district:
            kwargs["district"] = district
        institute_id = filters.get("institute_id")
        if institute_id:
            kwargs["institute_id"] = institute_id
            kwargs["distance_km"] = filters.get("distance_km", 3.0)

        # ── 硬约束字段 ──
        amenities = filters.get("amenities")
        if amenities and isinstance(amenities, list) and len(amenities) > 0:
            kwargs["amenities"] = amenities
        room_type = filters.get("room_type")
        if room_type:
            kwargs["room_type"] = room_type
        bathrooms = filters.get("bathrooms")
        if bathrooms is not None:
            kwargs["bathrooms"] = bathrooms
        area_min = filters.get("area_min")
        if area_min is not None:
            kwargs["area_min"] = float(area_min)
        area_max = filters.get("area_max")
        if area_max is not None:
            kwargs["area_max"] = float(area_max)
        min_lease = filters.get("min_lease_months")
        if min_lease is not None:
            kwargs["min_lease_months"] = int(min_lease)
        max_lease = filters.get("max_lease_months")
        if max_lease is not None:
            kwargs["max_lease_months"] = int(max_lease)
        available_from = filters.get("available_from")
        if available_from:
            kwargs["available_from"] = str(available_from)

        return kwargs

    async def _search_with_relaxation(
        self, query: str | None, filters: dict[str, Any], limit: int = 500,
    ) -> dict[str, Any]:
        """渐进放宽检索条件，直到找到足够的结果。"""
        rows: list = []
        relaxation_level = 0
        relaxed_fields: list[str] = []

        has_structured = any(
            filters.get(k) is not None and filters.get(k) != ""
            for k in ("district", "price_min", "price_max", "bedrooms", "property_type", "institute_id")
        )
        effective_query = query if not has_structured else None

        search_kwargs = self._build_search_kwargs(filters, limit=limit)
        try:
            rows = await self.property_service.search(query=effective_query, **search_kwargs)
        except Exception:
            logger.warning("检索失败，降级为纯条件筛选", exc_info=True)
            rows = await self.property_service.search(query=None, **search_kwargs)

        if len(rows) >= RELAXATION_MIN_RESULTS:
            return {"rows": rows, "relaxation_level": relaxation_level, "relaxed_fields": relaxed_fields}

        # 地理半径优先放宽
        geo_relaxed = False
        if filters.get("institute_id") and len(rows) < RELAXATION_MIN_RESULTS:
            current_dist = filters.get("distance_km", 3.0)
            for expand_km in (5.0, 10.0):
                if len(rows) >= RELAXATION_MIN_RESULTS:
                    break
                if current_dist < expand_km:
                    relaxed = dict(filters)
                    relaxed["distance_km"] = expand_km
                    relaxed_fields.append(f"搜索半径扩大到 {expand_km}km")
                    relaxation_level += 1
                    geo_relaxed = True
                    try:
                        rows = await self.property_service.search(query=None, **self._build_search_kwargs(relaxed, limit=limit))
                    except Exception:
                        pass
            if geo_relaxed and len(rows) >= RELAXATION_MIN_RESULTS:
                return {"rows": rows, "relaxation_level": relaxation_level, "relaxed_fields": relaxed_fields}

        # 逐级放宽
        relaxed = dict(filters)
        for relax_spec in RELAXATION_ORDER:
            if len(rows) >= RELAXATION_MIN_RESULTS:
                break
            key = relax_spec["key"]
            if key in relaxed:
                del relaxed[key]
                relaxed_fields.append(relax_spec["label"])
            elif key == "price_max" and relaxed.get("price_max") is not None:
                factor = relax_spec.get("expand_factor", 1.2)
                relaxed["price_max"] = int(float(relaxed["price_max"]) * factor)
                relaxed_fields.append(f"{relax_spec['label']} 扩大 {int((factor-1)*100)}%")
            relaxation_level += 1
            search_kwargs = self._build_search_kwargs(relaxed, limit=limit)
            has_any = any(relaxed.get(k) is not None and relaxed.get(k) != ""
                          for k in ("district", "price_min", "price_max", "bedrooms", "property_type", "institute_id"))
            relaxed_query = query if not has_any else None
            try:
                rows = await self.property_service.search(query=relaxed_query, **search_kwargs)
            except Exception:
                rows = await self.property_service.search(query=None, **search_kwargs)

        # 最终回退：提取英文关键词裸搜
        if len(rows) == 0 and query:
            import re as _re
            tokens = _re.findall(r'[A-Za-z0-9]+', query)
            acronyms = _re.findall(r'\b[A-Z]{2,5}\b', query)
            all_tokens = list(dict.fromkeys(acronyms + tokens))
            if all_tokens:
                short_query = ' '.join(all_tokens[:3])
                relaxation_level += 1
                relaxed_fields.append("关键词回退搜索")
                try:
                    keyword_rows = await self.property_service.search(query=short_query, limit=limit)
                    rows = [(prop, 0.5) for prop, _ in keyword_rows] if keyword_rows else []
                except Exception:
                    pass

        return {"rows": rows, "relaxation_level": relaxation_level, "relaxed_fields": relaxed_fields}

    @staticmethod
    def _validate_recommendations(recommendations: list[dict], candidate_snapshot: list[int]) -> tuple[list[dict], int]:
        """校验 LLM 推荐：所有房源必须在候选快照中。"""
        valid: list[dict] = []
        dropped = 0
        snapshot_set = set(candidate_snapshot) if candidate_snapshot else set()
        for rec in recommendations:
            if rec.get("property_id") in snapshot_set:
                valid.append(rec)
            else:
                logger.warning("一致性校验：LLM 编造了不在候选快照中的房源 property_id=%s", rec.get("property_id"))
                dropped += 1
        if dropped > 0:
            logger.warning("一致性校验：丢弃了 %d 条 LLM 幻觉推荐", dropped)
        return valid, dropped

    @staticmethod
    def _build_source_info(result_count: int, filters: dict[str, Any], relaxation_level: int, relaxed_fields: list[str]) -> str:
        """生成检索溯源信息"""
        parts = [f"\n\n---\n[检索] 本次基于 {result_count} 套房源检索"]
        filter_parts = []
        for key, label in {"district": "区域", "price_min": "最低预算", "price_max": "最高预算",
                            "bedrooms": "户型", "property_type": "类型"}.items():
            val = filters.get(key)
            if val is not None and val != "":
                if key in ("price_min", "price_max"):
                    val = f"¥{int(val):,}"
                elif key == "property_type":
                    val = {"apartment": "公寓", "house": "别墅", "studio": "单间", "shared": "合租"}.get(str(val), str(val))
                filter_parts.append(f"{label}: {val}")
        if filter_parts:
            parts.append("条件: " + " | ".join(filter_parts))
        if relaxation_level > 0 and relaxed_fields:
            parts.append(f"已放宽: {' → '.join(relaxed_fields)}")
        return "\n".join(parts)

    # ── 学校/机构查找 ──────────────────────────────────────────

    async def _lookup_institution(self, name: str) -> dict[str, Any] | None:
        """根据学校/机构名称模糊查找 institutes 表，返回 {id, name, lat, lng} 或 None"""
        from app.models.institute import Institute, InstituteStatus

        if not name or not name.strip():
            return None
        name = name.strip()

        # 1. 精确匹配 abbreviation（如 NUS、UCL）
        stmt = select(Institute).where(
            func.lower(Institute.abbreviation) == name.lower(),
            Institute.status == InstituteStatus.active,
        )
        result = await self.session.scalars(stmt)
        inst = result.first()
        if inst and inst.latitude is not None and inst.longitude is not None:
            return {"id": inst.id, "name": inst.name, "lat": float(inst.latitude), "lng": float(inst.longitude)}

        # 2. ILIKE 模糊匹配 name
        pattern = f"%{name}%"
        stmt = select(Institute).where(
            func.lower(Institute.name).ilike(pattern),
            Institute.status == InstituteStatus.active,
        )
        result = await self.session.scalars(stmt)
        inst = result.first()
        if inst and inst.latitude is not None and inst.longitude is not None:
            return {"id": inst.id, "name": inst.name, "lat": float(inst.latitude), "lng": float(inst.longitude)}

        # 3. ILIKE 模糊匹配 abbreviation
        stmt = select(Institute).where(
            func.lower(Institute.abbreviation).ilike(pattern),
            Institute.status == InstituteStatus.active,
        )
        result = await self.session.scalars(stmt)
        inst = result.first()
        if inst and inst.latitude is not None and inst.longitude is not None:
            return {"id": inst.id, "name": inst.name, "lat": float(inst.latitude), "lng": float(inst.longitude)}

        return None

    # ── 购物车 ────────────────────────────────────────────────────

    async def get_or_create_cart(self, user_id: int) -> AgentCart:
        stmt = (
            select(AgentCart)
            .where(AgentCart.user_id == user_id)
            .order_by(AgentCart.created_at.desc())
        )
        cart = (await self.session.scalars(stmt)).first()
        if cart is None:
            cart = AgentCart(user_id=user_id)
            self.session.add(cart)
            await self.session.commit()
            await self.session.refresh(cart)
        return cart

    async def add_to_cart(
        self, user_id: int, property_id: int, reason: str | None = None
    ) -> AgentCartItem:
        """加入购物车；重复添加返回已有项"""
        prop = await self.session.get(Property, property_id)
        if prop is None:
            raise ValueError("房源不存在")

        cart = await self.get_or_create_cart(user_id)
        stmt = select(AgentCartItem).where(
            AgentCartItem.cart_id == cart.id,
            AgentCartItem.property_id == property_id,
        )
        existing = (await self.session.scalars(stmt)).first()
        if existing is not None:
            return existing

        item = AgentCartItem(cart_id=cart.id, property_id=property_id, reason=reason)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_from_cart(self, user_id: int, property_id: int) -> bool:
        cart = await self.get_or_create_cart(user_id)
        stmt = select(AgentCartItem).where(
            AgentCartItem.cart_id == cart.id,
            AgentCartItem.property_id == property_id,
        )
        item = (await self.session.scalars(stmt)).first()
        if item is None:
            return False
        await self.session.delete(item)
        await self.session.commit()
        return True

    async def get_cart_items(self, user_id: int) -> tuple[AgentCart, list[AgentCartItem]]:
        cart = await self.get_or_create_cart(user_id)
        stmt = (
            select(AgentCartItem)
            .where(AgentCartItem.cart_id == cart.id)
            .order_by(AgentCartItem.created_at.asc())
        )
        items = list(await self.session.scalars(stmt))
        return cart, items

    # ── 意图解析 ──────────────────────────────────────────────────

    async def parse_user_intent(
        self, message: str, history: list[dict] | None = None
    ) -> dict[str, Any]:
        """判断用户意图（兼容旧接口，内部委托给 classify_message）。"""
        result = await self.classify_message(message, history)
        intent_map = {
            "search": "recommend", "manage_cart": "add_to_cart",
            "compare": "compare_cart", "faq": "faq", "general": "general",
        }
        old_intent = intent_map.get(result["intent"], "general")
        return {
            "intent": old_intent, "refs": result["refs"],
            "faq_id": result.get("faq_topic"), "faq_confidence": result.get("faq_confidence"),
            "sub_intent": result["sub_intent"], "stage": result["stage"],
            "complexity": result["complexity"], "routing": result["routing"],
        }

    # ── 推荐 ──────────────────────────────────────────────────────

    async def recommend_properties(
        self, message: str, filters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """检索 + LLM 推荐。"""
        filters = filters or {}
        llm = get_llm_service()

        # ── LLM 提取结构化筛选条件 ──
        extracted: dict[str, Any] = {}
        if llm.is_available:
            try:
                extracted = await llm.complete_json(EXTRACT_FILTERS_PROMPT, message, temperature=0.0, max_tokens=400)
                if not isinstance(extracted, dict):
                    extracted = {}
            except Exception:
                logger.debug("LLM 提取搜索条件失败")

        # 前端 filters 优先级高于 LLM 提取
        district = filters.get("district") or extracted.get("district") or None
        if district and district.lower().strip() in _EN_TO_CN_CITY:
            district = _EN_TO_CN_CITY[district.lower().strip()]
        price_min = filters.get("price_min") or extracted.get("price_min")
        price_max = filters.get("price_max") or extracted.get("price_max")
        bedrooms = filters.get("bedrooms") or extracted.get("bedrooms")
        property_type = filters.get("property_type") or extracted.get("property_type") or None

        # ── 硬约束字段合并（filters 优先，extracted 兜底） ──
        amenities: list[str] | None = filters.get("amenities") or extracted.get("amenities") or None
        room_type: str | None = filters.get("room_type") or extracted.get("room_type") or None
        bathrooms: int | None = filters.get("bathrooms") or extracted.get("bathrooms") or None
        area_min: float | None = filters.get("area_min") or extracted.get("area_min") or None
        area_max: float | None = filters.get("area_max") or extracted.get("area_max") or None
        min_lease_months: int | None = filters.get("min_lease_months") or extracted.get("min_lease_months") or None
        max_lease_months: int | None = filters.get("max_lease_months") or extracted.get("max_lease_months") or None
        available_from: str | None = filters.get("available_from") or extracted.get("available_from") or None

        # ── 学校/机构查找 ──
        institution_name = filters.get("institution") or extracted.get("institution") or None
        distance_km = extracted.get("distance_km", 3.0)
        if not isinstance(distance_km, (int, float)) or distance_km < 0.5 or distance_km > 10.0:
            distance_km = 3.0
        institute_id: int | None = None

        # ── 通勤约束提取 ──
        commute_mode = extracted.get("commute_mode") or None
        commute_minutes = extracted.get("commute_minutes") or None
        if commute_minutes is not None:
            try:
                commute_minutes = int(commute_minutes)
            except (TypeError, ValueError):
                commute_minutes = None
        institute_info: dict[str, Any] | None = None

        if institution_name and not district:
            try:
                inst = await self._lookup_institution(institution_name)
                if inst:
                    institute_id = inst["id"]
                    institute_info = inst
                    # 通勤模式指定时使用宽松预筛选半径
                    if commute_mode and commute_mode in _COMMUTE_PRE_FILTER_KM:
                        distance_km = max(distance_km, _COMMUTE_PRE_FILTER_KM[commute_mode])
                    logger.info("机构匹配: %s → id=%s, distance=%skm", institution_name, institute_id, distance_km)
            except Exception:
                logger.exception("机构查找失败: %s", institution_name)

        # 查询文本：学校名加入 query 增强语义（降级路径）
        query_parts = [message]
        if filters.get("country"):
            query_parts.append(str(filters["country"]))
        if institution_name and not institute_id:
            query_parts.append(institution_name)
        query_text = " ".join(p for p in query_parts if p)

        # 搜索：有机构时走地理半径，否则走 v2 渐进放宽检索
        merged_filters = {
            "district": district, "price_min": price_min, "price_max": price_max,
            "bedrooms": bedrooms, "property_type": property_type,
            "institute_id": institute_id, "distance_km": distance_km,
            # 硬约束字段（不会在放宽流程中被删除，只会在最终兜底时放宽）
            "amenities": amenities, "room_type": room_type,
            "bathrooms": bathrooms,
            "area_min": area_min, "area_max": area_max,
            "min_lease_months": min_lease_months, "max_lease_months": max_lease_months,
            "available_from": available_from,
        }

        if institute_id is not None:
            search_kwargs: dict[str, Any] = {
                "district": district,
                "price_min": Decimal(str(price_min)) if price_min is not None else None,
                "price_max": Decimal(str(price_max)) if price_max is not None else None,
                "bedrooms": bedrooms,
                "property_type": property_type,
                "status": PropertyStatus.available.value,
                "limit": 500,
                # 硬约束字段
                "amenities": amenities,
                "room_type": room_type,
                "bathrooms": bathrooms,
                "area_min": area_min,
                "area_max": area_max,
                "min_lease_months": min_lease_months,
                "max_lease_months": max_lease_months,
                "available_from": available_from,
            }
            try:
                rows = await self._geo_search(institute_id, distance_km, search_kwargs)
            except Exception:
                logger.exception("地理搜索失败，降级")
                rows = []
            if len(rows) < 5:
                for expand_km in (5.0, 10.0, 20.0, 50.0):
                    if len(rows) >= 5:
                        break
                    try:
                        rows = await self._geo_search(institute_id, expand_km, search_kwargs)
                    except Exception:
                        pass
            relaxation_level = 0
            relaxed_fields: list[str] = []
        else:
            relax_result = await self._search_with_relaxation(query=query_text, filters=merged_filters)
            rows = relax_result["rows"]
            relaxation_level = relax_result["relaxation_level"]
            relaxed_fields = relax_result["relaxed_fields"]

        candidates = [prop for prop, _sim in rows]

        # ── 通勤时间过滤（仅当有学校 + 通勤约束时触发）──
        if commute_mode and commute_minutes and institute_info:
            candidates = await self._filter_by_commute(
                origin_lat=institute_info["lat"],
                origin_lng=institute_info["lng"],
                candidates=candidates,
                mode=commute_mode,
                max_minutes=commute_minutes,
                country=institute_info.get("country"),
                city=institute_info.get("city_cn"),
            )
            logger.info("通勤过滤: mode=%s max=%smin result=%s", commute_mode, commute_minutes, len(candidates))

        # ── 得分间隙检测 ──
        scores = [float(sim) if sim is not None else 0.0 for _prop, sim in rows]
        score_gap = detect_score_gap(scores)

        # ── 安全兜底判断 ──
        if self._safe_fallback.should_fallback(documents=candidates, top_score=score_gap["top_score"], relaxation_level=relaxation_level):
            fallback_reply = self._safe_fallback.build_fallback_response(query=message, active_filters=merged_filters, relaxation_level=relaxation_level)
            return {
                "reply": fallback_reply, "recommendations": [], "ai_available": True,
                "extracted_filters": extracted, "top_picks": [],
                "score_gap": score_gap, "relaxation_level": relaxation_level, "source_info": "",
            }

        # ── AI 精选 Top 3（确定性评分） ──
        top_picks = _score_properties(candidates, filters, extracted)
        top_picks_payload = [
            {"property_id": tp["property"].id, "match_reason": " · ".join(tp["highlights"]),
             "pros": tp["highlights"], "cons": [], "property": tp["property"]}
            for tp in top_picks
        ]

        # ── 全部匹配房源（完整返回，"查看所有"展开使用） ──
        all_recs = [
            {"property_id": p.id, "match_reason": "", "pros": [], "cons": [], "property": p}
            for p in candidates
        ]

        candidate_ids = [p.id for p in candidates]
        source_info = self._build_source_info(len(candidates), merged_filters, relaxation_level, relaxed_fields)

        # ── LLM 生成回复（基于 Top 3 精选） ──
        if llm.is_available:
            try:
                top_props = [tp["property"] for tp in top_picks]
                user_prompt = (
                    f"用户需求：{message}\n"
                    f"检索结果：共 {len(candidates)} 套，覆盖 {len(set(p.district for p in candidates if p.district))} 个区域\n"
                    f"精选房源（按匹配度排序，最多介绍 3 套）：\n{_props_text(top_props[:3])}"
                )
                result = await llm.complete_json(RECOMMEND_SYSTEM_PROMPT, user_prompt, max_tokens=800)
                reply = str(result.get("reply") or f"为您找到 {len(candidates)} 套符合需求的房源。") + source_info
            except Exception:
                logger.exception("LLM 推荐生成失败")
                reply = f"为您找到 {len(candidates)} 套符合需求的房源。{AI_UNAVAILABLE_HINT}{source_info}"
        else:
            reply = f"为您找到 {len(candidates)} 套符合需求的房源。{AI_UNAVAILABLE_HINT}{source_info}"

        return {
            "reply": reply, "recommendations": all_recs, "ai_available": llm.is_available,
            "extracted_filters": extracted, "top_picks": top_picks_payload,
            "score_gap": score_gap, "relaxation_level": relaxation_level,
            "candidate_snapshot": candidate_ids, "source_info": source_info,
        }

    async def _geo_search(
        self, institute_id: int, distance_km: float, base_kwargs: dict[str, Any]
    ) -> list[tuple[Property, float | None]]:
        """执行地理半径搜索（调用 PropertyService 的 Haversine 精筛路径）"""
        from app.services.geo_utils import hav_distance
        from app.models.institute import Institute

        inst = await self.session.get(Institute, institute_id)
        if not inst or inst.latitude is None or inst.longitude is None:
            return []

        # 先用宽松条件获取候选（不传 district 以免过滤掉）
        search_kwargs = dict(base_kwargs)
        search_kwargs.pop("district", None)
        search_kwargs["limit"] = search_kwargs.get("limit", 500) * 3  # 多取候选
        rows = await self.property_service.search(query=None, **search_kwargs)

        # Haversine 精筛
        inst_lat, inst_lng = float(inst.latitude), float(inst.longitude)
        results: list[tuple[Property, float]] = []
        for prop, _sim in rows:
            if prop.latitude is None or prop.longitude is None:
                continue
            dist = hav_distance(inst_lat, inst_lng, float(prop.latitude), float(prop.longitude))
            if dist <= distance_km:
                results.append((prop, dist))

        results.sort(key=lambda x: x[1])  # 按距离升序
        return [(p, d) for p, d in results[:500]]

    async def _filter_by_commute(
        self,
        origin_lat: float, origin_lng: float,
        candidates: list[Property],
        mode: str, max_minutes: int,
        country: str | None = None, city: str | None = None,
    ) -> list[Property]:
        """用真实路线 API 计算通勤时间并过滤（带渐进放宽 + 多引擎降级）。

        降级链：网络探测 → 主 API → 备选 API → ORS → Haversine 兜底
        """
        from app.services.commute_service import (
            CommuteDestination,
            calculate_commute_batch_resilient,
        )

        destinations = [
            CommuteDestination(dest_id=p.id, lat=float(p.latitude), lng=float(p.longitude))
            for p in candidates
            if p.latitude is not None and p.longitude is not None
        ]
        if not destinations:
            return candidates

        batch_result = await calculate_commute_batch_resilient(
            origin_lat, origin_lng, destinations, country=country, city=city,
        )

        result_by_id: dict[int | str, Any] = {}
        for r in batch_result.results:
            result_by_id[r.dest_id] = r

        mode_key = {"walking": "walk_min", "bicycling": "bike_min",
                     "driving": "drive_min", "transit": "transit_min"}[mode]

        for relax_minutes in (max_minutes, max_minutes * _COMMUTE_RELAX_MULTIPLIERS[1],
                               max_minutes * _COMMUTE_RELAX_MULTIPLIERS[2],
                               max_minutes * _COMMUTE_RELAX_MULTIPLIERS[3]):
            passed: list[Property] = []
            for p in candidates:
                if p.id not in result_by_id:
                    continue
                r = result_by_id[p.id]
                if getattr(r, mode_key, 999) <= relax_minutes:
                    object.__setattr__(p, '_commute_time', getattr(r, mode_key))
                    object.__setattr__(p, '_commute_source', r.source)
                    passed.append(p)
            if len(passed) >= 5 or relax_minutes >= max_minutes * 4:
                passed.sort(key=lambda x: getattr(x, '_commute_time', 999))
                return passed

        # 兜底：全部按通勤时间排序
        for p in candidates:
            if p.id in result_by_id:
                r = result_by_id[p.id]
                object.__setattr__(p, '_commute_time', getattr(r, mode_key, 999))
                object.__setattr__(p, '_commute_source', r.source)
        candidates.sort(key=lambda x: getattr(x, '_commute_time', 999))
        return candidates

    # ── 对比 ──────────────────────────────────────────────────────

    async def compare_cart(
        self,
        user_id: int,
        property_ids: list[int] | None = None,
        priority: str | None = None,
    ) -> dict[str, Any]:
        """对比房源。

        - 传入 property_ids 时：只对比这些房源（可来自推荐横条或购物车，不要求已加购）。
        - 未传时：对比整个购物车（兼容旧行为，自然语言「对比一下」也走这里）。
        - priority：用户优先级（balanced/budget/commute/space），决定加权评分的权重。
        购物车为空或所选房源无效时抛 ValueError。
        """
        if property_ids:
            props: list[Property] = []
            for pid in dict.fromkeys(property_ids):  # 去重保序
                prop = await self.session.get(Property, pid)
                if prop is not None:
                    props.append(prop)
            if len(props) < 2:
                raise ValueError("请至少选择 2 套有效房源进行对比")
            return await self._compare_props(props, priority)

        _cart, items = await self.get_cart_items(user_id)
        if not items:
            raise ValueError("购物车为空，请先添加房源再对比")

        props = []
        for item in items:
            prop = await self.session.get(Property, item.property_id)
            if prop is not None:
                props.append(prop)
        if not props:
            raise ValueError("购物车中的房源已不存在")

        return await self._compare_props(props, priority)

    async def _gather_compare_metrics(
        self, props: list[Property]
    ) -> tuple[list[PropertyMetrics], dict[int, dict]]:
        """为对比补充真实数据：POI 通勤距离 + 机构评价聚合。

        返回 (metrics 列表, {property_id: 展示用附加信息})
        """
        ids = [p.id for p in props]

        pois: dict[int, PropertyPOI] = {}
        try:
            rows = await self.session.scalars(
                select(PropertyPOI).where(PropertyPOI.property_id.in_(ids))
            )
            pois = {poi.property_id: poi for poi in rows}
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
            poi = pois.get(p.id)
            transit = nearest_transit_meters(poi.poi_data if poi else None)
            rating, count = (None, 0)
            if p.institute_id and p.institute_id in rating_by_inst:
                rating, count = rating_by_inst[p.institute_id]
            metrics.append(
                PropertyMetrics(
                    property_id=p.id,
                    price=float(p.price_monthly),
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

    async def _compare_props(
        self, props: list[Property], priority: str | None = None
    ) -> dict[str, Any]:
        """对一组房源做对比。

        评分与解释分离：先用真实数据（价格/面积/POI 通勤/机构评价）按用户优先级
        算出确定性加权得分；LLM 只负责解释优劣势，分数不允许它改。LLM 不可用时
        用规则模板生成解释，分数完全一致。
        """
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

        llm = get_llm_service()
        if llm.is_available:
            try:
                lines = []
                for i, p in enumerate(props, 1):
                    d = _property_to_dict(p)
                    e = extras[p.id]
                    s = scores[p.id]
                    lines.append(
                        f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | "
                        f"月租: ¥{d['price_monthly']} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
                        f"面积: {d['area_sqm'] or '未知'}㎡ | 通勤: {e['commute'] or '无数据'} | "
                        f"评价: {(str(e['rating']) + '分/' + str(e['review_count']) + '条') if e['rating'] is not None else '暂无'} | "
                        f"简介: {d['description'] or '无'}\n"
                        f"   系统得分（禁止修改）: 综合 {s['total']} | "
                        + " ".join(f"{DIMENSION_LABELS[k]} {v}" for k, v in s["breakdown"].items())
                    )
                user_prompt = (
                    f"用户优先级：{PRIORITY_LABELS[pr]}\n\n"
                    f"待对比房源（数据库真实数据 + 系统计算得分）：\n" + "\n".join(lines)
                )
                result = await llm.complete_json(COMPARE_SYSTEM_PROMPT, user_prompt, max_tokens=2000)

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
                    dim_analysis = _build_dimension_analysis(props, scores, extras, pr, result)
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

    def _rule_based_compare(
        self,
        props: list[Property],
        scores: dict[int, dict],
        extras: dict[int, dict],
        priority: str,
    ) -> dict[str, Any]:
        """LLM 不可用时的规则解释：得分同一套加权公式，优劣势按分项名次生成"""
        by_id = {p.id: p for p in props}

        # 各维度冠军（得分并列都算）
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
            item = {
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
            }
            items_out.append(item)

        prices = [float(p.price_monthly) for p in props]
        winner = max(props, key=lambda p: scores[p.id]["total"])
        fake_result = {
            "summary": f"按「{PRIORITY_LABELS[priority]}」共对比 {len(props)} 套房源，价格区间 ¥{min(prices):.0f} - ¥{max(prices):.0f}。{AI_UNAVAILABLE_HINT}",
            "recommendation": f"按「{PRIORITY_LABELS[priority]}」综合得分最高的是「{winner.title}」（{scores[winner.id]['total']} 分）。",
        }

        return {
            "summary": fake_result["summary"],
            "dimension_analysis": _build_dimension_analysis(props, scores, extras, priority, fake_result),
            "items": items_out,
            "recommendation": fake_result["recommendation"],
            "ai_available": False,
            "priority": priority,
        }

    # ── 会话消息主流程 ────────────────────────────────────────────

    async def _last_recommendations(self, session_id: int) -> list[dict]:
        """取会话中最近一条带推荐列表的 assistant 消息 metadata"""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == ChatMessageRole.assistant,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(20)
        )
        for msg in await self.session.scalars(stmt):
            meta = msg.metadata_ or {}
            recs = meta.get("recommendations")
            if recs:
                return recs
        return []

    async def _history(self, session_id: int, limit: int = 10) -> list[dict]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        msgs = list(await self.session.scalars(stmt))
        return [
            {"role": m.role.value, "content": m.content}
            for m in reversed(msgs)
            if m.role in (ChatMessageRole.user, ChatMessageRole.assistant)
        ]

    def _resolve_refs(
        self, refs: list[int], explicit_ids: list[int], last_recs: list[dict]
    ) -> list[int]:
        """把序号引用解析成 property_id 列表"""
        ids = list(explicit_ids)
        rec_ids = [r.get("property_id") for r in last_recs if r.get("property_id")]
        if -1 in refs:  # 全部
            ids.extend(rec_ids)
        else:
            for ref in refs:
                if 1 <= ref <= len(rec_ids):
                    ids.append(rec_ids[ref - 1])
        return list(dict.fromkeys(ids))

    @staticmethod
    def _faq_answer(entry: FaqEntry) -> dict[str, Any]:
        """FAQ 强命中：返回占位政策答案 + 页面深链 + 后续建议 chips"""
        return {
            "reply": entry.answer,
            "quick_replies": list(entry.next_chips),
            "links": [{"label": link.label, "to": link.to} for link in entry.links],
            "faq_id": entry.id,
        }

    @staticmethod
    def _faq_confirm(hits: list[FaqEntry]) -> dict[str, Any]:
        """FAQ 弱命中：不硬答，反问确认，chips 一点即精确进入工作流"""
        if len(hits) == 1:
            reply = f"你是想了解「{hits[0].chip}」吗？点下面的按钮确认，或者换个说法描述你的问题。"
        else:
            names = "、".join(f"「{e.chip}」" for e in hits)
            reply = f"你想了解的是 {names} 中的哪一个？点下面的按钮选择，或补充说明你的问题。"
        return {
            "reply": reply,
            "quick_replies": [e.chip for e in hits],
            "links": [],
            "faq_id": None,
        }

    async def handle_message(
        self,
        chat_session: ChatSession,
        user_id: int,
        message: str,
        filters: dict[str, Any] | None = None,
        search_state: Any = None,
        compare_property_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Agent 消息主入口：意图识别 → 分发处理 → 持久化对话（v2 漏斗架构）"""
        history = await self._history(chat_session.id)
        explicit_ids = _parse_property_ids(message)

        recommendations: list[dict] = []
        cart_changed = False
        ai_available = True
        quick_replies: list[str] = []
        links: list[dict] = []
        faq_id: str | None = None
        extracted_filters: dict | None = None
        top_picks: list[dict] = []
        source_info = ""
        score_gap: dict | None = None
        relaxation_level = 0
        candidate_snapshot: list[int] = []

        # ── 统一分类（v2：意图 + 阶段 + 路由） ──
        classify_result = await self.classify_message(message, history)

        # 更新 SearchState 漏斗阶段
        stage_result = {"stage": classify_result["stage"], "confidence": classify_result["confidence"],
                        "reasoning": classify_result.get("reasoning", "")}
        if search_state is not None:
            from app.services.search_state import FunnelStage
            stage_val = classify_result["stage"]
            if stage_val in FunnelStage.__members__.values():
                search_state.funnel_stage = FunnelStage(stage_val)

        new_intent = classify_result["intent"]
        sub_intent = classify_result["sub_intent"]
        refs = classify_result["refs"]
        routing = classify_result["routing"]
        faq_topic = classify_result.get("faq_topic")

        # FAQ 规则匹配优先
        faq_payload: dict[str, Any] | None = None
        strength, faq_hits = match_faq(message)
        if strength == "strong":
            intent, refs = "faq", []
            faq_payload = self._faq_answer(faq_hits[0])
        elif strength == "weak":
            intent, refs = "faq", []
            faq_payload = self._faq_confirm(faq_hits)
        elif new_intent == "manage_cart":
            intent = "add_to_cart" if sub_intent == "add" else "remove_from_cart" if sub_intent == "remove" else "compare_cart"
        elif new_intent == "compare":
            intent = "compare_cart"
        elif new_intent == "search":
            intent = "recommend"
        elif new_intent == "faq":
            if faq_topic and get_faq(faq_topic) is not None:
                intent = "faq"
                faq_payload = self._faq_answer(faq_topic)
            else:
                intent = "general"
        else:
            intent = "general"

        # 前端候选清单显式触发对比（点击"对比所选"按钮）→ 强制对比意图
        if compare_property_ids and len(compare_property_ids) >= 2:
            intent = "compare_cart"

        if intent == "faq" and faq_payload is not None:
            reply = faq_payload["reply"]
            quick_replies = faq_payload["quick_replies"]
            links = faq_payload["links"]
            faq_id = faq_payload["faq_id"]

        elif intent == "recommend":
            result = await self.recommend_properties(message, filters)
            reply = result["reply"]
            recommendations = result["recommendations"]
            ai_available = result["ai_available"]
            extracted_filters = result.get("extracted_filters")
            top_picks = result.get("top_picks", [])
            source_info = result.get("source_info", "")
            score_gap = result.get("score_gap")
            relaxation_level = result.get("relaxation_level", 0)
            candidate_snapshot = result.get("candidate_snapshot", [])
            # 更新 SearchState
            if search_state is not None and candidate_snapshot:
                search_state.candidate_snapshot = candidate_snapshot
                search_state.last_result_count = len(candidate_snapshot)
                search_state.last_relaxation_level = relaxation_level
                search_state.last_score_gap = score_gap
                if extracted_filters:
                    for k, v in extracted_filters.items():
                        if v is not None and v != "" and v != 0:
                            search_state.active_filters[k] = v

        elif intent == "add_to_cart":
            last_recs = await self._last_recommendations(chat_session.id)
            target_ids = self._resolve_refs(refs, explicit_ids, last_recs)
            if not target_ids and len(last_recs) == 1:
                target_ids = [last_recs[0]["property_id"]]
            if not target_ids:
                reply = "请告诉我要加入哪套房源，比如「把第一个加入购物车」。"
            else:
                added_titles = []
                reason_by_id = {
                    r["property_id"]: r.get("match_reason") for r in last_recs
                }
                for pid in target_ids:
                    try:
                        await self.add_to_cart(user_id, pid, reason_by_id.get(pid))
                        prop = await self.session.get(Property, pid)
                        added_titles.append(prop.title if prop else f"房源 {pid}")
                        cart_changed = True
                    except ValueError:
                        continue
                if added_titles:
                    reply = f"已将「{'」「'.join(added_titles)}」加入候选清单。需要继续找房还是对比一下？"
                else:
                    reply = "没有找到对应的房源，请确认序号或房源编号。"

        elif intent == "remove_from_cart":
            _cart, items = await self.get_cart_items(user_id)
            cart_ids = [it.property_id for it in items]
            target_ids = list(explicit_ids)
            if -1 in refs:
                target_ids.extend(cart_ids)
            else:
                for ref in refs:
                    if 1 <= ref <= len(cart_ids):
                        target_ids.append(cart_ids[ref - 1])
            target_ids = list(dict.fromkeys(target_ids))
            if not target_ids:
                reply = "请告诉我要移除哪套房源，比如「把第一个从清单里移除」。"
            else:
                removed = 0
                for pid in target_ids:
                    if await self.remove_from_cart(user_id, pid):
                        removed += 1
                        cart_changed = True
                reply = f"已从候选清单移除 {removed} 套房源。" if removed else "候选清单中没有找到对应的房源。"

        elif intent == "compare_cart":
            try:
                # 若前端传了 compare_property_ids，则只对比这些房源（来自候选清单勾选）
                compare = await self.compare_cart(user_id, property_ids=compare_property_ids)
                ai_available = compare["ai_available"]
                # 优先使用维度组织的分析文本，降级时用逐房源描述
                dim_text = compare.get("dimension_analysis", "")
                if dim_text:
                    reply = dim_text
                else:
                    lines = [compare["summary"]]
                    for it in compare["items"]:
                        lines.append(
                            f"「{it['title']}」推荐指数 {it['score']}：优势 {'、'.join(it['pros']) or '—'}；"
                            f"劣势 {'、'.join(it['cons']) or '—'}"
                            + (f"；适合{it['best_for']}" if it.get("best_for") else "")
                        )
                    lines.append(compare["recommendation"])
                    reply = "\n".join(x for x in lines if x)
            except ValueError as e:
                reply = str(e)

        else:  # general
            llm = get_llm_service()
            if llm.is_available:
                try:
                    msgs = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]
                    msgs.extend(history)
                    msgs.append({"role": "user", "content": message})
                    reply = await llm.complete_text(msgs)
                except Exception:
                    logger.exception("LLM 普通咨询回复失败")
                    reply = "我是租房推荐助手，可以告诉我您想找的地区、预算和户型，我来帮您推荐房源。"
            else:
                reply = "我是租房推荐助手，可以告诉我您想找的地区、预算和户型，我来帮您推荐房源。"
                ai_available = False

        # 持久化对话（推荐列表存 metadata，供后续"把第一个加入购物车"引用）
        user_msg = ChatMessage(
            session_id=chat_session.id,
            role=ChatMessageRole.user,
            content=message,
            metadata_={"filters": filters or {}},
        )
        assistant_msg = ChatMessage(
            session_id=chat_session.id,
            role=ChatMessageRole.assistant,
            content=reply,
            metadata_={
                "intent": intent, "faq_id": faq_id,
                "funnel_stage": stage_result.get("stage", "explore"),
                "relaxation_level": relaxation_level, "score_gap": score_gap,
                "candidate_snapshot": candidate_snapshot,
                "recommendations": [
                    {"property_id": r["property_id"], "match_reason": r.get("match_reason", "")}
                    for r in recommendations
                ],
            },
        )
        self.session.add_all([user_msg, assistant_msg])
        await self.session.commit()

        return {
            "reply": reply, "intent": intent, "recommendations": recommendations,
            "cart_changed": cart_changed, "ai_available": ai_available,
            "quick_replies": quick_replies, "links": links,
            "extracted_filters": extracted_filters, "top_picks": top_picks,
            "funnel_stage": stage_result.get("stage", "explore"),
            "score_gap": score_gap, "relaxation_level": relaxation_level,
            "candidate_snapshot": candidate_snapshot, "source_info": source_info,
        }

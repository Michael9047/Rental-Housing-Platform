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
from app.services.compare_scoring import (
    DIMENSION_LABELS,
    PRIORITY_LABELS,
    PropertyMetrics,
    format_commute,
    nearest_transit_meters,
    normalize_priority,
)
from app.services.llm_service import get_llm_service
from app.services.preference_state import build_preference_views
from app.services.property_service import PropertyService
from app.services.property_fact_service import (
    PropertyFactBundle,
    PropertyFactService,
    satisfies_poi_requirements,
)
from app.services.safe_fallback import SafeFallback
from app.services.score_gap import detect_score_gap
from app.services.scoring_service import ScoringService

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
UNIFIED_CLASSIFIER_PROMPT = """你是面向留学生的海外租房平台的对话路由器。分析用户消息，输出分类结果。

══════════════════════════════
示例（Few-Shot）
══════════════════════════════

示例1：
用户：「帮我看看园区有没有2000以内的单间」
→ {"intent":"search","sub_intent":"filter","stage":"narrow","complexity":0.5,"confidence":0.95,"routing":"agent","faq_topic":null,"faq_confidence":null,"refs":[],"reasoning":"明确找房需求，含区域+预算+户型"}

示例2：
用户：「押金一般什么时候退」
→ {"intent":"faq","sub_intent":"deposit","stage":"general","complexity":0.1,"confidence":0.9,"routing":"fast","faq_topic":"deposit","faq_confidence":"high","refs":[],"reasoning":"政策咨询，押金相关"}

示例3：
用户：「第二套和第三套哪个更好」
→ {"intent":"compare","sub_intent":"specific","stage":"compare","complexity":0.6,"confidence":0.85,"routing":"agent","faq_topic":null,"faq_confidence":null,"refs":[2,3],"reasoning":"对比两套特定房源"}

示例4：
用户：「hi」
→ {"intent":"general","sub_intent":"greeting","stage":"general","complexity":0.05,"confidence":0.95,"routing":"fast","faq_topic":null,"faq_confidence":null,"refs":[],"reasoning":"简单问候"}

══════════════════════════════
只输出 JSON
══════════════════════════════
{
  "intent": "search | manage_cart | compare | faq | general",
  "sub_intent": "见下方各 intent 取值",
  "stage": "explore | calibrate | narrow | compare | decide | general",
  "complexity": 0.0-1.0,
  "confidence": 0.0-1.0,
  "routing": "fast | agent",
  "faq_topic": null,
  "faq_confidence": null,
  "refs": [],
  "reasoning": "简短理由，≤20字"
}

【search】找房需求
  sub_intent: "explore"(刚开始看) | "browse"(随便看看) | "filter"(有明确条件) | "detail"(问特定房源) | "commute"(通勤相关)
  stage: explore(刚起步)→calibrate(了解行情)→narrow(明确条件)→compare(对比中)→decide(快定了)
  complexity: explore=0.3, filter=0.5, commute=0.6

【manage_cart】购物车操作
  sub_intent: "add" | "remove" | "view"

【compare】对比房源
  sub_intent: "cart"(对比购物车中全部) | "specific"(对比特定几套，填refs)

【faq】政策/流程问题
  sub_intent: "how_to_find" | "booking" | "contract" | "deposit" | "refund" | "fees" | "other"
  faq_confidence: "high"(很确定) | "low"(拿不准)

【general】闲聊/问候
  sub_intent: "chitchat" | "greeting" | "other"

routing: "fast"(FAQ/闲聊→直接回复) | "agent"(搜索/对比→走Agent管道)"""

RECOMMEND_SYSTEM_PROMPT = """你是面向留学生的海外租房推荐助手。系统已从数据库检索出候选房源（附真实数据）。挑选最匹配的 3 套，用口语化中文撰写推荐。

══════════════════════════════
示例（Few-Shot）
══════════════════════════════

示例1 — 结果充足（≥5套）：
候选：学校周边 8 套，2000 以内单间，含公寓A/公寓B/公寓C等
→ reply: 「学校周边 2000 以内的单间帮你筛出来了，一共 8 套，这 3 套最值得看：\n\n通勤首选 — 公寓A，单间 ¥1800/月，步行到校 10 分钟，独卫精装，家具齐全\n\n性价比 — 公寓B，单间 ¥1500/月，楼下就是商业街，适合预算紧的同学\n\n舒适型 — 公寓C，单间 ¥1950/月，面积大采光好，安静适合学习\n\n上面可以横滑看卡片对比，有中意的加购物车，我帮你详细对比。」

示例2 — 结果偏少（1-4套）：
候选：稍远区域 2 套，1000 以内合租
→ reply: 「这个价位合租选择不多，就这 2 套：\n\n经济实惠 — 小区D，合租次卧 ¥850/月，包水电网，公交到校 15 分钟\n\n配套好 — 小区E，合租主卧 ¥950/月，独卫，楼下超市餐馆齐全\n\n这个价位选择确实少。要不要把预算提到 1200？可以多出 5 套。」

示例3 — 无结果：
候选：0 套
→ reply: 「园区独卫单间目前在 1500 以内确实没有。建议：1）预算提到 1800，翰林缘就有独卫单间了；2）考虑合租，1500 能拿下独卫主卧；3）换到吴中，同样价格选择更多。你想试试哪个方向？」
→ recommendations: []

══════════════════════════════
回复结构（三段式，口语化）
══════════════════════════════

1. 开头：总结匹配情况，数量+价格范围+区域。语气像朋友聊天。
2. 逐套：<亮点标签> — <位置>，<户型> ¥<价格>/月，补充面积、房屋简介、租期、房内设施，
   以及有真实数据支持的通勤和周边设施。每套突出差异化优势，不要重复。
3. 收尾：引导下一步。结果多→引导细化条件；结果少→给放宽建议。

══════════════════════════════
严格规则
══════════════════════════════
1. 只推荐候选列表里的 property_id，禁止编造。
2. 基于真实字段（价格、区域、户型、面积、通勤、设施）。
3. 价格用"¥"，不要用"元"或"块"。
4. 候选为空→recommendations=[], reply 给具体放宽建议（见示例3）。
5. 精选最多 3 套，按匹配度降序。
6. 回复 250-400 字。结果少或周边数据缺失时不要强行凑字数，诚实告知+给建议。
7. 不要用"为你找到""亲爱的用户"等客服腔。

只输出 JSON：
{
  "intent": "recommend",
  "reply": "三段式口语推荐回复",
  "recommendations": [
    {"property_id": 1, "match_reason": "通勤首选，步行10分钟到校", "pros": ["精装独卫","家具齐全"], "cons": ["面积偏小"]}
  ]
}"""

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

GENERAL_SYSTEM_PROMPT = """你是面向留学生的海外租房顾问，用口语化中文简洁回答。

示例1：
用户：「hi」
→ 回复：「嗨！想在学校附近租房吗？告诉我你的预算和需求，我帮你筛。」

示例2：
用户：「学校附近住哪里比较好」
→ 回复：「看你预算和需求：学校周边公寓走路10分钟但偏贵，稍远一点公交15分钟性价比高很多。你预算多少？要独卫吗？」

规则：
- 1-2 句话，口语化
- 不编造房源信息
- 如果用户想找房，引导描述地区、预算、户型"""

# ── 从用户消息中提取结构化搜索条件 ────────────────────────
EXTRACT_FILTERS_PROMPT = """从用户消息中提取结构化的租房搜索条件。

══════════════════════════════
示例（Few-Shot）
══════════════════════════════

示例1：
用户：「园区2000以内带独卫的单间」
→ {"district":"园区","price_max":2000,"amenities":["独立卫浴"],"property_type":"studio","price_min":null,"bedrooms":null,"institution":null,"distance_km":3.0,"commute_mode":null,"commute_minutes":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null}

示例2：
用户：「文星广场附近1500左右能养猫的合租」
→ {"district":"文星","price_min":1350,"price_max":1650,"amenities":["宠物友好"],"property_type":"shared","bedrooms":null,"institution":null,"distance_km":null,"commute_mode":null,"commute_minutes":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null}

示例3：
用户：「学校步行15分钟以内，预算2500，要独卫和阳台」
→ {"district":null,"price_max":2500,"amenities":["独立卫浴","阳台"],"institution":"悉尼大学","commute_mode":"walking","commute_minutes":15,"distance_km":5.0,"property_type":null,"bedrooms":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null}

══════════════════════════════
输出格式
══════════════════════════════
只输出 JSON（不要 markdown）：
{
  "district": "区域名称，如 园区/吴中/文星/翰林。无法确定则为 null",
  "price_min": 最低月租整数，null=未提及,
  "price_max": 最高月租整数，null=未提及,
  "bedrooms": 卧室数整数，null=未提及,
  "property_type": "apartment/house/studio/shared 之一，null=未提及",
  "institution": "大学/学校名称，null=未提及",
  "distance_km": 距学校搜索半径(km)，默认3.0。commute_mode不为null时用宽松值",
  "commute_mode": "walking/bicycling/driving/transit 之一，null=未提交通勤",
  "commute_minutes": 通勤时间上限(分钟)，null=未提及,
  "amenities": ["标准设施名列表，见下方映射"],
  "room_type": "studio/ensuite/1bed/2bed/3bed+/shared 或 null",
  "bathrooms": 卫生间数整数，null=未提及,
  "area_min": 最小面积(㎡)整数，null=未提及,
  "area_max": 最大面积(㎡)整数，null=未提及,
  "min_lease_months": 最短租期(月)整数，null=未提及
}

══════════════════════════════
关键规则
══════════════════════════════
- district 是行政区划，不要把学校名填进去。"NUS附近"→district=null,institution="NUS"
- "1500左右" → price_min=1350, price_max=1650（±10%区间）
- "便宜点"/"尽量便宜" → price_max 设为用户预算的80%，或 price_min=null, price_max=1500
- 不确定时填 null

══════════════════════════════
设施映射（amenities 标准值）
══════════════════════════════
"能养猫"/"养狗"/"宠物" → ["宠物友好"]
"可以做饭"/"有厨房" → ["独立厨房"]
"独卫"/"独立卫生间" → ["独立卫浴"]
"有wifi"/"能上网"/"宽带" → ["WiFi"]
"有空调"/"冷气" → ["空调"]
"有洗衣机" → ["洗衣机"]
"有冰箱" → ["冰箱"]
"有阳台"/"露台" → ["阳台"]
"有电梯" → ["电梯"]
"有车位"/"能停车" → ["车位"]
"有健身房"/"gym" → ["健身房"]
"有泳池"/"游泳" → ["泳池"]
"家具齐全"/"拎包入住" → ["家具齐全"]
"禁烟"/"无烟" → ["禁烟"]
"精装"/"装修好" → ["精装修"]
未提及设施 → amenities: []

══════════════════════════════
通勤推断
══════════════════════════════
"步行30分钟内" → commute_mode="walking", commute_minutes=30, distance_km=5.0
"骑车15分钟" → commute_mode="bicycling", commute_minutes=15, distance_km=10.0
"开车10分钟" → commute_mode="driving", commute_minutes=10, distance_km=20.0
"公交20分钟"/"地铁半小时" → commute_mode="transit", commute_minutes=20/30, distance_km=15.0
"步行距离"(未提分钟) → commute_mode="walking", commute_minutes=20, distance_km=5.0
commute_mode 不为 null → distance_km 用宽松预筛选半径"""

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
    r"找|搜|推荐|租|房源|房子|居室|单间|公寓|合租|别墅|预算|地铁|公交|通勤|学校|大学|附近|周边|配套|超市|健身|医院|医疗|阳台|独卫|重新|去掉|不要|[0-9一二两三四五]\s*室|元|块|㎡|平米|平方"
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
            commute_source = getattr(p, '_commute_source', None)
            source_note = "（路线API批量计算）" if commute_source in {"amap_api", "ors_api"} else "（估算）"
            line += f" | 通勤: {commute_time}分钟{source_note}"
        facts = getattr(p, "_property_facts", None)
        if isinstance(facts, dict):
            poi = facts.get("poi") or {}
            poi_parts: list[str] = []
            for key, label in (
                ("nearest_transit_m", "交通"),
                ("nearest_supermarket_m", "超市"),
                ("nearest_gym_m", "健身房"),
                ("nearest_medical_m", "医疗"),
            ):
                if poi.get(key) is not None:
                    poi_parts.append(f"最近{label}{poi[key]}米")
            if poi_parts:
                line += " | 周边: " + "、".join(poi_parts)
            completeness = facts.get("data_completeness") or {}
            if not completeness.get("poi_cache_available", False):
                line += " | 周边数据: 待补充"
        lines.append(line)
    return "\n".join(lines)


def _build_deterministic_recommendation_reply(
    top_picks: list[dict[str, Any]],
    candidate_count: int,
) -> str:
    """LLM 不可用时也用真实字段生成较完整的房源介绍。"""
    if not top_picks:
        return "当前没有找到完全符合条件的房源，可以适当放宽预算、区域或户型后再试。"

    type_labels = {
        "apartment": "公寓",
        "house": "别墅",
        "studio": "单间",
        "shared": "合租",
    }
    lines = [f"共匹配到 {candidate_count} 套房源，先重点看看下面 {len(top_picks)} 套："]
    for index, item in enumerate(top_picks, 1):
        property_obj = item["property"]
        property_type = (
            property_obj.property_type.value
            if hasattr(property_obj.property_type, "value")
            else str(property_obj.property_type)
        )
        specs = [
            f"¥{float(property_obj.price_monthly):,.0f}/月",
            f"{property_obj.bedrooms or 0}室{property_obj.bathrooms or 0}卫",
            type_labels.get(property_type, property_type),
        ]
        if property_obj.area_sqm is not None:
            specs.append(f"{float(property_obj.area_sqm):g}㎡")

        line = f"{index}. **{property_obj.title}**｜{'｜'.join(specs)}，位于{property_obj.district}。"
        description = " ".join((property_obj.description or "").split())
        if description:
            line += description[:90] + ("…" if len(description) > 90 else "") + "。"

        highlights = [str(value) for value in item.get("highlights", []) if value]
        if highlights:
            line += "推荐点：" + "、".join(highlights[:3]) + "。"

        facts = getattr(property_obj, "_property_facts", None)
        if isinstance(facts, dict):
            completeness = facts.get("data_completeness") or {}
            poi = facts.get("poi") or {}
            nearby: list[str] = []
            for key, label in (
                ("nearest_transit_m", "公共交通"),
                ("nearest_supermarket_m", "超市"),
                ("nearest_gym_m", "健身房"),
                ("nearest_medical_m", "医疗设施"),
            ):
                distance = poi.get(key)
                if distance is not None:
                    nearby.append(f"最近{label}约{distance}米")
            if completeness.get("poi_cache_available") and nearby:
                line += "周边：" + "、".join(nearby) + "。"
            else:
                line += "真实周边数据待补充。"

            commute = facts.get("commute")
            if isinstance(commute, dict):
                source_note = "估算" if commute.get("source") == "haversine_fallback" else "路线数据"
                line += (
                    f"通勤（{source_note}）：驾车约{commute.get('drive_min')}分钟，"
                    f"公交约{commute.get('transit_min')}分钟。"
                )
        lines.append(line)

    lines.append("房源卡片可以横向滑动查看更多，也可以加入候选清单后统一对比。")
    return "\n\n".join(lines)


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
    soft_constraints: list[dict[str, Any]] | None = None,
    fact_bundles: dict[int, PropertyFactBundle] | None = None,
) -> list[dict[str, Any]]:
    """兼容旧调用方；实际算法统一由 ScoringService 承载。"""
    return ScoringService.score_recommendations(
        candidates,
        filters,
        extracted,
        soft_constraints=soft_constraints,
        fact_bundles=fact_bundles,
    )


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
        self,
        query: str | None,
        filters: dict[str, Any],
        limit: int = 500,
        protected_fields: set[str] | None = None,
    ) -> dict[str, Any]:
        """渐进放宽非硬条件；protected_fields 中的硬约束绝不删除。"""
        rows: list = []
        relaxation_level = 0
        relaxed_fields: list[str] = []
        protected_fields = protected_fields or set()

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
            if key in protected_fields:
                continue
            if relaxed.get(key) is None:
                continue
            if key == "price_max" and relax_spec.get("expand_factor"):
                factor = relax_spec.get("expand_factor", 1.2)
                relaxed["price_max"] = int(float(relaxed["price_max"]) * factor)
                relaxed_fields.append(f"{relax_spec['label']} 扩大 {int((factor-1)*100)}%")
            else:
                del relaxed[key]
                relaxed_fields.append(relax_spec["label"])
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
                    keyword_rows = await self.property_service.search(
                        query=short_query,
                        **self._build_search_kwargs(relaxed, limit=limit),
                    )
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
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        extracted_filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """检索 + LLM 推荐。"""
        filters = filters or {}
        llm = get_llm_service()

        # Supervisor 已传入 FilterAgent 结果时不重复调用 LLM；保留旧调用方兼容路径。
        extracted: dict[str, Any] = extracted_filters or {}
        if extracted_filters is None and llm.is_available:
            try:
                extracted = await llm.complete_json(EXTRACT_FILTERS_PROMPT, message, temperature=0.0, max_tokens=400)
                if not isinstance(extracted, dict):
                    extracted = {}
            except Exception:
                logger.debug("LLM 提取搜索条件失败")

        # 前端 Filter Bar 始终视为硬约束；FilterAgent 的软偏好只参与排序。
        preference_views = build_preference_views(extracted, filters)
        all_preferences = preference_views.all_values
        hard_values = preference_views.hard_values
        resolved_preferences = {
            **all_preferences,
            "hard_filters": list(hard_values.keys()),
            "soft_preferences": list(dict.fromkeys(
                constraint["field"] for constraint in preference_views.soft_constraints
            )),
            "preference_constraints": preference_views.constraints,
        }

        district = hard_values.get("district") or None
        if district and district.lower().strip() in _EN_TO_CN_CITY:
            district = _EN_TO_CN_CITY[district.lower().strip()]
        price_min = hard_values.get("price_min")
        price_max = hard_values.get("price_max")
        bedrooms = hard_values.get("bedrooms")
        property_type = hard_values.get("property_type") or None

        amenities: list[str] | None = hard_values.get("amenities") or None
        room_type: str | None = hard_values.get("room_type") or None
        bathrooms: int | None = hard_values.get("bathrooms")
        area_min: float | None = hard_values.get("area_min")
        area_max: float | None = hard_values.get("area_max")
        min_lease_months: int | None = hard_values.get("min_lease_months")
        max_lease_months: int | None = hard_values.get("max_lease_months")
        available_from: str | None = hard_values.get("available_from")

        # ── 学校/机构查找 ──
        institution_name = all_preferences.get("institution") or None
        distance_km = all_preferences.get("distance_km", 3.0)
        if not isinstance(distance_km, (int, float)) or distance_km < 0.5 or distance_km > 10.0:
            distance_km = 3.0
        institute_id: int | None = None

        # ── 通勤约束提取 ──
        commute_mode = all_preferences.get("commute_mode") or None
        commute_minutes = all_preferences.get("commute_minutes") or None
        if commute_minutes is not None:
            try:
                commute_minutes = int(commute_minutes)
            except (TypeError, ValueError):
                commute_minutes = None
        institute_info: dict[str, Any] | None = None

        if institution_name:
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
        if all_preferences.get("country"):
            query_parts.append(str(all_preferences["country"]))
        if institution_name and not institute_id:
            query_parts.append(institution_name)
        query_text = " ".join(p for p in query_parts if p)

        # 搜索：有机构时走地理半径，否则走 v2 渐进放宽检索
        use_geo_prefilter = bool(
            institute_id is not None
            and ("institution" in hard_values or commute_minutes is not None)
        )
        merged_filters = {
            "district": district, "price_min": price_min, "price_max": price_max,
            "bedrooms": bedrooms, "property_type": property_type,
            "institute_id": institute_id if use_geo_prefilter else None,
            "distance_km": distance_km,
            "amenities": amenities, "room_type": room_type,
            "bathrooms": bathrooms,
            "area_min": area_min, "area_max": area_max,
            "min_lease_months": min_lease_months, "max_lease_months": max_lease_months,
            "available_from": available_from,
        }

        if use_geo_prefilter and institute_id is not None:
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
            # 默认半径只是预筛选；用户显式给出硬距离时不得自动扩大。
            if len(rows) < 5 and "distance_km" not in hard_values:
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
            relax_result = await self._search_with_relaxation(
                query=query_text,
                filters=merged_filters,
                protected_fields=set(hard_values),
            )
            rows = relax_result["rows"]
            relaxation_level = relax_result["relaxation_level"]
            relaxed_fields = relax_result["relaxed_fields"]

        # POI 摘要和路线 API 都是批量路径；控制候选池，避免逐房源外部请求失控。
        candidates = [prop for prop, _sim in rows][:50]
        fact_bundles = await PropertyFactService(self.session).build_bundles(
            candidates,
            origin_lat=institute_info.get("lat") if institute_info else None,
            origin_lng=institute_info.get("lng") if institute_info else None,
            country=(candidates[0].country if candidates else None) or all_preferences.get("country"),
            city=institute_info.get("city_cn") if institute_info else None,
        )
        for prop in candidates:
            bundle = fact_bundles[prop.id]
            object.__setattr__(prop, "_property_facts", bundle.to_dict())
            if commute_mode and bundle.commute:
                commute_value = bundle.commute.minutes_for(commute_mode)
                if commute_value is not None:
                    object.__setattr__(prop, "_commute_time", commute_value)
                    object.__setattr__(prop, "_commute_source", bundle.commute.source)

        # 硬 POI/通勤条件在真实事实返回后严格执行，不做自动放宽。
        hard_poi_requirements = hard_values.get("poi_requirements") or []
        if hard_poi_requirements:
            candidates = [
                prop for prop in candidates
                if satisfies_poi_requirements(fact_bundles[prop.id], hard_poi_requirements)
            ]
        hard_commute_minutes = hard_values.get("commute_minutes")
        # 没有起点坐标就算不出通勤时间，此时 fact_bundles 里 commute 全是 None，
        # 硬过滤会把候选清空。用户常说"通勤30分钟以内"却不提学校（FilterAgent 的
        # prompt 又明确把"以内"判为 hard），所以这不是边角情况：无起点时跳过该约束，
        # 而不是返回 0 套房源。
        if hard_commute_minutes is not None and institute_info:
            selected_mode = commute_mode or "transit"
            candidates = [
                prop for prop in candidates
                if fact_bundles[prop.id].commute is not None
                and fact_bundles[prop.id].commute.minutes_for(selected_mode) is not None
                and fact_bundles[prop.id].commute.minutes_for(selected_mode) <= int(hard_commute_minutes)
            ]
        elif hard_commute_minutes is not None:
            logger.info(
                "通勤硬约束 %s 分钟被跳过：未识别到起点机构（原始输入 institution=%r）",
                hard_commute_minutes, institution_name,
            )
        if commute_mode:
            candidates.sort(key=lambda prop: getattr(prop, "_commute_time", 10**9))

        # ── 得分间隙检测 ──
        candidate_ids_for_score = {prop.id for prop in candidates}
        scores = [
            float(sim) if sim is not None else 0.0
            for prop, sim in rows
            if prop.id in candidate_ids_for_score
        ]
        score_gap = detect_score_gap(scores)

        # ── 安全兜底判断 ──
        if self._safe_fallback.should_fallback(documents=candidates, top_score=score_gap["top_score"], relaxation_level=relaxation_level):
            fallback_reply = self._safe_fallback.build_fallback_response(query=message, active_filters=merged_filters, relaxation_level=relaxation_level)
            return {
                "reply": fallback_reply, "recommendations": [], "ai_available": llm.is_available,
                "extracted_filters": resolved_preferences, "top_picks": [],
                "score_gap": score_gap, "relaxation_level": relaxation_level, "source_info": "",
            }

        # ── AI 精选 Top 3（确定性评分） ──
        top_picks = ScoringService.score_recommendations(
            candidates,
            filters,
            resolved_preferences,
            soft_constraints=preference_views.soft_constraints,
            fact_bundles=fact_bundles,
        )
        top_picks_payload = [
            {"property_id": tp["property"].id, "match_reason": " · ".join(tp["highlights"]),
             "pros": tp["highlights"], "cons": [], "property": tp["property"],
             "facts": fact_bundles[tp["property"].id].to_dict()}
            for tp in top_picks
        ]

        # ── 全部匹配房源（完整返回，"查看所有"展开使用） ──
        all_recs = [
            {"property_id": p.id, "match_reason": "", "pros": [], "cons": [], "property": p,
             "facts": fact_bundles[p.id].to_dict()}
            for p in candidates
        ]

        candidate_ids = [p.id for p in candidates]
        source_info = self._build_source_info(len(candidates), merged_filters, relaxation_level, relaxed_fields)
        poi_cache_count = sum(
            fact_bundles[prop.id].data_completeness.poi_cache_available for prop in candidates
        )
        commute_sources = sorted({
            fact_bundles[prop.id].commute.source
            for prop in candidates
            if fact_bundles[prop.id].commute is not None
        })
        source_info += f"\n[事实] POI缓存覆盖 {poi_cache_count}/{len(candidates)} 套"
        if commute_sources:
            source_info += f" | 通勤来源: {', '.join(commute_sources)}"

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
                reply = (
                    _build_deterministic_recommendation_reply(top_picks, len(candidates))
                    + AI_UNAVAILABLE_HINT
                    + source_info
                )
        else:
            reply = (
                _build_deterministic_recommendation_reply(top_picks, len(candidates))
                + AI_UNAVAILABLE_HINT
                + source_info
            )

        return {
            "reply": reply, "recommendations": all_recs, "ai_available": llm.is_available,
            "extracted_filters": resolved_preferences, "top_picks": top_picks_payload,
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

        # 先用 SQL 条件获取候选；显式 district 属于硬约束，必须保留。
        search_kwargs = dict(base_kwargs)
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
        scores = ScoringService.score_comparison(metrics, pr)

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

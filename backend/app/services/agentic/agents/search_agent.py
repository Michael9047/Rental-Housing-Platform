"""搜索 Agent —— 完整搜索管线（提取条件 → 检索+放宽 → 通勤过滤 → 评分 → LLM 推荐）

Phase 5: 从 AgentService 迁移全部搜索逻辑，独立于 AgentService。
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any


def build_search_text(room) -> str:
    """将 Room + Institute + UnitType 三层信息拼接为 embedding 用文本。

    写入 rooms.embedding 前调用。搜什么就编码什么。
    """
    parts = []
    if room.title: parts.append(room.title)
    if room.institute_name: parts.append(room.institute_name)
    if room.district: parts.append(f"区域: {room.district}")
    if room.city: parts.append(f"城市: {room.city}")
    if room.country: parts.append(f"国家: {room.country}")
    if room.property_type: parts.append(room.property_type)
    if room.bedrooms: parts.append(f"{room.bedrooms}室")
    if room.bathrooms: parts.append(f"{room.bathrooms}卫")
    if room.area_sqm: parts.append(f"{room.area_sqm}平米")
    if room.institute_amenities: parts.append(f"配套: {room.institute_amenities}")
    if room.description: parts.append(room.description[:300])
    sym = get_symbol(getattr(room, 'currency', None))
    if room.price_monthly: parts.append(f"月租: {sym}{float(room.price_monthly):.0f}")
    return " | ".join(p for p in parts if p)


def build_unit_type_search_text(institute: Any, unit_type: Any) -> str:
    """将 Institute + UnitType 拼接为 embedding 文本。

    户型是最小的可租单元模板，向量化后实现「找类似户型」的语义检索。
    """
    parts = []
    # 公寓维度
    if institute.name: parts.append(institute.name)
    if institute.name_cn: parts.append(institute.name_cn)
    if institute.district: parts.append(f"区域: {institute.district}")
    if institute.city: parts.append(f"城市: {institute.city}")
    if institute.country: parts.append(f"国家: {institute.country}")
    if institute.amenities: parts.append(f"公寓配套: {', '.join(institute.amenities)}")
    if institute.description: parts.append(institute.description[:300])
    # 户型维度
    if unit_type.name: parts.append(f"户型: {unit_type.name}")
    if unit_type.bedrooms: parts.append(f"{unit_type.bedrooms}室")
    if unit_type.bathrooms: parts.append(f"{unit_type.bathrooms}卫")
    if unit_type.area_sqm: parts.append(f"{unit_type.area_sqm}平米")
    if unit_type.hall_count: parts.append(f"{unit_type.hall_count}厅")
    if unit_type.base_rent: parts.append(f"标准月租: {unit_type.currency or '¥'}{float(unit_type.base_rent):.0f}")
    if unit_type.special_offer: parts.append(f"优惠: {unit_type.special_offer}")
    if unit_type.amenities: parts.append(f"户型配套: {', '.join(unit_type.amenities)}")
    if unit_type.description: parts.append(unit_type.description[:300])
    return " | ".join(p for p in parts if p)


async def generate_unit_type_embedding(session, unit_type_id: int) -> str | None:
    """为户型生成 embedding 向量并写入 unit_types 表。

    拼接 Institute + UnitType 文本 → EmbeddingService → 写入 unit_types.embedding。
    房源导入成功后异步调用。
    """
    from sqlalchemy import select
    from app.models.unit_type import UnitType
    from app.models.institute import Institute
    from app.services.embedding_service import EmbeddingService
    import json

    ut = await session.get(UnitType, unit_type_id)
    if ut is None:
        return None
    inst = await session.get(Institute, ut.institute_id)
    if inst is None:
        return None

    text = build_unit_type_search_text(inst, ut)
    if not text.strip():
        return None

    try:
        emb_svc = EmbeddingService()
        vec = await emb_svc.generate_embedding(text)
        if vec is None:
            return None
        ut.embedding = json.dumps(vec)
        await session.commit()
        logger.info("UnitType #%s embedding generated (%d chars)", unit_type_id, len(text))
        return ut.embedding
    except Exception:
        logger.exception("UnitType #%s embedding 生成失败", unit_type_id)
        return None

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institute import Institute, InstituteStatus
from app.models.property import Property, PropertyStatus
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult, AgentError, AgentErrorType
from app.services.agentic.shared import property_to_dict
from app.services.llm_service import get_llm_service
from app.services.property_service import PropertyService
from app.services.currency import resolve_search_price, get_symbol
from app.services.safe_fallback import SafeFallback
from app.services.score_gap import detect_score_gap

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_HINT = "（AI 分析暂不可用，已按筛选条件为您检索）"

# ── 配置常量 ────────────────────────────────────────────────────
RELAXATION_MIN_RESULTS = 5
RELAXATION_ORDER: list[dict] = [
    {"key": "district", "label": "区域"},
    {"key": "property_type", "label": "房源类型"},
    {"key": "bedrooms", "label": "户型"},
    {"key": "price_max", "label": "预算上限", "expand_factor": 1.2},
]
_COMMUTE_PRE_FILTER_KM: dict[str, float] = {
    "walking": 5.0, "bicycling": 10.0, "driving": 20.0, "transit": 15.0,
}
_COMMUTE_RELAX_MULTIPLIERS = (1, 2, 3, 4)
_EN_TO_CN_CITY: dict[str, str] = {
    "london": "伦敦", "hong kong": "香港", "hk": "香港",
    "singapore": "新加坡", "sg": "新加坡",
    "los angeles": "洛杉矶", "la": "洛杉矶",
    "san francisco": "旧金山", "sf": "旧金山",
}

# 区域 → 默认币种
_DISTRICT_CURRENCY: dict[str, str] = {
    "伦敦": "GBP", "新加坡": "SGD", "洛杉矶": "USD",
    "硅谷": "USD", "伯克利": "USD", "香港": "HKD",
    "苏州": "CNY", "园区": "CNY",
}
_COUNTRY_CURRENCY: dict[str, str] = {
    "GB": "GBP", "SG": "SGD", "US": "USD", "HK": "HKD", "CN": "CNY",
}


def _infer_currency(district: str | None, country: str | None) -> str:
    """从区域和国家推断房源币种。"""
    if district:
        for key, cur in _DISTRICT_CURRENCY.items():
            if key in str(district):
                return cur
    if country and str(country).upper() in _COUNTRY_CURRENCY:
        return _COUNTRY_CURRENCY[str(country).upper()]
    return "GBP"  # 默认英镑（当前主力市场）

# ── 通勤查表（大学 → 区域 → 步行/公交分钟） ──
# 优先查表，未命中再走 API
_COMMUTE_TABLE: dict[str, dict[str, tuple[int, int]]] = {
    # 伦敦
    "UCL": {
        "布鲁姆斯伯里": (5, 10), "国王十字": (12, 15), "尤斯顿": (8, 10),
        "卡姆登": (15, 20), "霍尔本": (10, 15), "伊斯灵顿": (20, 25),
        "帕丁顿": (25, 30), "肖尔迪奇": (25, 30),
    },
    "Imperial": {
        "南肯辛顿": (5, 8), "伯爵宫": (10, 12), "汉默史密斯": (15, 20),
        "帕丁顿": (20, 25), "切尔西": (8, 12),
    },
    "LSE": {
        "霍尔本": (5, 10), "滑铁卢": (15, 20), "伦敦桥": (20, 25),
        "肖尔迪奇": (20, 25), "布鲁姆斯伯里": (15, 20),
    },
    "KCL": {
        "滑铁卢": (5, 10), "伦敦桥": (10, 15), "霍尔本": (15, 20),
        "白教堂": (20, 25), "南华克": (10, 15),
    },
    "QMUL": {
        "白教堂": (10, 15), "肖尔迪奇": (15, 20), "伦敦桥": (20, 30),
        "斯特拉特福德": (15, 20),
    },
    # 新加坡
    "NUS": {
        "金文泰": (12, 15), "西海岸": (8, 10), "女皇镇": (15, 25),
        "荷兰村": (15, 20), "波那维斯达": (10, 15), "杜佛": (6, 10),
        "巴西班让": (12, 18), "红山": (20, 30), "武吉知马": (15, 25),
    },
    "NTU": {
        "裕廊西": (12, 15), "文礼": (8, 12), "湖畔": (15, 20),
        "先驱": (5, 10), "裕廊东": (20, 25), "裕华": (10, 15),
    },
    "SMU": {
        "武吉士": (5, 10), "多美歌": (5, 10), "梧槽": (8, 12),
        "市中心": (10, 15),
    },
    "SUTD": {
        "樟宜": (10, 15), "四美": (15, 20), "淡滨尼": (20, 25),
    },
}


def _lookup_commute(university: str, district: str) -> tuple[int, int] | None:
    """查通勤表，返回 (walk_min, transit_min) 或 None。"""
    abbr = university.upper().strip() if university else ""
    # 精确匹配缩写
    if abbr in _COMMUTE_TABLE:
        for area, (walk, transit) in _COMMUTE_TABLE[abbr].items():
            if area in str(district or ""):
                return (walk, transit)
    # 模糊匹配大学名
    for uni_key, areas in _COMMUTE_TABLE.items():
        if uni_key.lower() in str(university or "").lower():
            for area, (walk, transit) in areas.items():
                if area in str(district or ""):
                    return (walk, transit)
    return None


# ── Prompts ──────────────────────────────────────────────────────

EXTRACT_FILTERS_PROMPT = """从用户消息中提取结构化的租房搜索条件，按优先级分三级。

P0 硬约束（必须满足，否则排除）：amenities / room_type / bathrooms / commute / institution
P1 软偏好（尽量满足，影响排序）：price / district / bedrooms / area / property_type
P2 点缀（加分项，仅描述亮点）：精装修 / 高楼层 / 阳台 / 泳池 / 健身房 / 采光安静

示例1：「UCL附近1500镑以内studio，一定要独卫，最好步行15分钟以内」
→ {"district":"伦敦","price_max":1500,"currency":"GBP","amenities":["独立卫浴"],"property_type":"studio","institution":"UCL","commute_mode":"walking","commute_minutes":15,"hard_filters":["amenities","institution","property_type"],"soft_preferences":["price","commute"],"p2_highlights":[]}

示例2：「NUS附近800新币，最好精装带泳池」
→ {"district":"新加坡","price_max":800,"currency":"SGD","institution":"NUS","hard_filters":["institution"],"soft_preferences":["price"],"p2_highlights":["精装修","泳池"]}

只输出 JSON。设施映射：独卫→独立卫浴, wifi→WiFi。currency：¥/人民币/元/块→CNY, £/英镑/镑→GBP, S$/新币→SGD。未提及时填 null。"""

RECOMMEND_SYSTEM_PROMPT = """你是留学生租房推荐助手。根据提供的结构化数据撰写推荐回复。严格按此结构：

## 结构

### 一、概览（1-2句）
「{school}周边 {budget} 以内的 {type} 共 {total} 种户型，精选 {top_n} 套深度分析。」
如果结果偏多→引导细化条件；结果偏少→诚实告知+给放宽建议。

### 二、逐套深度分析（每套独立，用「---」分隔）

每套按此顺序：
**✅ P0 硬约束全部满足**：区域({district}) | 预算({sym}{price}/月，在 {sym}{budget} 以内) | {bedrooms}室 | {其他P0条件}...
**📊 P1 软偏好匹配**：
  · 预算贴合度：{sym}{price}/月 vs 预算 {sym}{budget} — {评价}
  · 面积：{area_sqm}㎡ — {评价}
  · 通勤：到{school}步行{walk}分钟/公交{transit}分钟 — {评价}
  · {其他P1维度逐一列出，每项一句话评价}
**🏢 公寓设施**：{列出 institute.amenities 中与用户相关的，标注匹配点}
**🏠 户型设施**：{列出 unit_type.amenities，标注用户提到的}
**🛒 周边配套**：{如有POI数据} 步行可达超市/餐厅等；{无则写"周边配套数据待补充"}
**🚌 通勤详情**：{walk/transit分钟数 + 交通方式建议}
**✨ 亮点**：{1-2个p2点缀或其他户型没有的优势}

### 三、横向对比（表格式）

| 维度 | 最佳 | 说明 |
|------|------|------|
| 🚌 通勤 | {最优名} | 步行{min}分钟/公交{min}分钟到{school} |
| 💰 性价比 | {最优名} | {sym}{price}/月 {bedrooms}室 |
| 📐 面积 | {最优名} | {area_sqm}㎡ |
| 🏠 设施 | {最优名} | {突出设施} |
| 🔒 安全 | {最优名} | {safety_score}/5.0 |

### 四、Takeaway
2-3句回顾用户需求，给出明确推荐和原因。如：「综合来看，{winner}最匹配你的需求——{核心理由}。如果你更看重{次要优先级}，{alternative}也不错。要不要把这3套加入候选清单详细对比？」

规则：
- 只基于给出的真实数据，禁止编造价格/距离/设施
- 口语化中文，用「你」不用「您」
- 价格带币种符号
- 500-900字
- 如果某维度数据缺失，写"暂无数据"不要跳过

只输出 JSON：{"reply": "完整回复"}"""


# ── 确定性评分（模块级函数，SearchAgent + ToolRegistry 共用） ──

def score_properties(
    candidates: list[Property],
    filters: dict[str, Any],
    extracted: dict[str, Any],
    embedding_scores: dict[int, float] | None = None,
) -> list[dict[str, Any]]:
    """对候选房源进行综合评分：embedding × 0.6 + P1规则 × 0.4。

    返回 top 3 附带亮点理由。
    """
    if not candidates:
        return []

    emb = embedding_scores or {}
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

        p1_rule = price_score * 0.40 + space_score * 0.20 + facility_score * 0.20 + 60 * 0.20
        emb_score = emb.get(p.id, 0.5) * 100  # 0-1 → 0-100
        total = emb_score * 0.6 + p1_rule * 0.4

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

        scored.append({"property": p, "score": round(total, 1), "highlights": highlights[:3]})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


def _props_text(props: list[Property]) -> str:
    """将房源列表转为 LLM 可读的文本摘要。"""
    lines = []
    for i, p in enumerate(props, 1):
        d = property_to_dict(p)
        sym = get_symbol(d.get('currency'))
        line = (
            f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | "
            f"月租: {sym}{d['price_monthly']} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
            f"面积: {d['area_sqm'] or '未知'}㎡ | 简介: {d['description'] or '无'}"
        )
        commute_time = getattr(p, '_commute_time', None)
        if commute_time is not None:
            source_note = "（路线API实时计算）" if getattr(p, '_commute_source', None) == "api" else "（估算）"
            line += f" | 通勤: {commute_time}分钟{source_note}"
        lines.append(line)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# SearchAgent
# ═══════════════════════════════════════════════════════════════════

class SearchAgent(BaseAgent):
    """房源搜索 Agent。完整管线：提取条件 → 检索+放宽 → 通勤过滤 → 评分 → LLM 推荐。

    替代 AgentService 中的 recommend_properties / _search_with_relaxation
    / _geo_search / _filter_by_commute / _lookup_institution。
    """

    name = "search_agent"
    description = "房源搜索 + 渐进放宽 + 通勤过滤 + 质量评分。独立于 AgentService。"
    tools = [
        "extract_filters", "property_search", "score_properties",
        "gap_detect", "safe_fallback_check", "query_rewrite",
        "poi_lookup", "commute_calc",
    ]

    def __init__(self, session: AsyncSession | None = None, tool_registry=None) -> None:
        super().__init__(tool_registry)
        self._session = session
        self._property_service: PropertyService | None = None
        self._safe_fallback = SafeFallback()

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("SearchAgent 未绑定 DB session")
        return self._session

    @property
    def property_service(self) -> PropertyService:
        if self._property_service is None:
            self._property_service = PropertyService(self.session)
        return self._property_service

    # ── 主入口 ────────────────────────────────────────────────────

    async def search(
        self, message: str, filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """检索 + LLM 推荐。逻辑与 AgentService.recommend_properties() 完全一致。"""
        filters = filters or {}
        llm = get_llm_service()

        # 1. LLM 提取结构化筛选条件
        extracted: dict[str, Any] = {}
        if llm.is_available:
            try:
                extracted = await llm.complete_json(EXTRACT_FILTERS_PROMPT, message, temperature=0.0, max_tokens=400)
                if not isinstance(extracted, dict):
                    extracted = {}
            except Exception:
                logger.debug("LLM 提取搜索条件失败")

        district = filters.get("district") or extracted.get("district") or None
        if district and district.lower().strip() in _EN_TO_CN_CITY:
            district = _EN_TO_CN_CITY[district.lower().strip()]
        price_min = filters.get("price_min") or extracted.get("price_min")
        price_max = filters.get("price_max") or extracted.get("price_max")
        bedrooms = filters.get("bedrooms") or extracted.get("bedrooms")
        property_type = filters.get("property_type") or extracted.get("property_type") or None

        # ── 货币换算 ──
        # 推断房源目标币种：从 district/country 推断，默认 GBP
        target_currency = _infer_currency(district, filters.get("country"))
        if price_min is not None:
            price_min = resolve_search_price(message, float(price_min), target_currency)
        if price_max is not None:
            price_max = resolve_search_price(message, float(price_max), target_currency)

        # 硬约束字段合并
        amenities: list[str] | None = filters.get("amenities") or extracted.get("amenities") or None
        room_type: str | None = filters.get("room_type") or extracted.get("room_type") or None
        bathrooms: int | None = filters.get("bathrooms") or extracted.get("bathrooms") or None
        area_min: float | None = filters.get("area_min") or extracted.get("area_min") or None
        area_max: float | None = filters.get("area_max") or extracted.get("area_max") or None
        min_lease_months: int | None = filters.get("min_lease_months") or extracted.get("min_lease_months") or None
        max_lease_months: int | None = filters.get("max_lease_months") or extracted.get("max_lease_months") or None
        available_from: str | None = filters.get("available_from") or extracted.get("available_from") or None

        # 2. 学校查找（查 universities 表获取坐标）
        institution_name = filters.get("institution") or extracted.get("institution") or None
        distance_km = extracted.get("distance_km", 3.0)
        if not isinstance(distance_km, (int, float)) or distance_km < 0.5 or distance_km > 50.0:
            distance_km = 3.0

        commute_mode = extracted.get("commute_mode") or None
        commute_minutes = extracted.get("commute_minutes") or None
        if commute_minutes is not None:
            try:
                commute_minutes = int(commute_minutes)
            except (TypeError, ValueError):
                commute_minutes = None

        # 大学坐标（P0 距离硬约束）
        uni_info: dict[str, Any] | None = None
        if institution_name:
            try:
                uni_info = await self._lookup_institution(institution_name)
                if uni_info:
                    if commute_mode and commute_mode in _COMMUTE_PRE_FILTER_KM:
                        distance_km = max(distance_km, _COMMUTE_PRE_FILTER_KM[commute_mode])
                    logger.info("大学匹配: %s → %s (%.4f, %.4f) distance=%skm",
                                institution_name, uni_info["name"], uni_info["lat"], uni_info["lng"], distance_km)
            except Exception:
                logger.exception("大学查找失败: %s", institution_name)

        # 大学匹配成功后，district 改为大学所在城市
        # 避免 LLM 把 "NUS" 之类当作 district → ILIKE 匹配注定 0 结果
        # 精确位置由 bounding box 保证，district 只负责城市级筛选
        if uni_info:
            uni_city = (uni_info.get("city") or "").strip()
            uni_city_cn = _EN_TO_CN_CITY.get(uni_city.lower(), uni_city)
            if uni_city_cn:
                district = uni_city_cn

        # 查询文本
        query_parts = [message]
        if filters.get("country"):
            query_parts.append(str(filters["country"]))
        if institution_name and not uni_info:
            query_parts.append(institution_name)
        query_text = " ".join(p for p in query_parts if p)

        # P0 硬约束构建
        merged_filters = {
            "district": district, "price_min": price_min, "price_max": price_max,
            "bedrooms": bedrooms, "property_type": property_type,
            "amenities": amenities, "room_type": room_type,
            "bathrooms": bathrooms, "area_min": area_min, "area_max": area_max,
            "min_lease_months": min_lease_months, "max_lease_months": max_lease_months,
            "available_from": available_from,
            # 大学距离约束（P0 硬筛选）
            "near_lat": uni_info["lat"] if uni_info else None,
            "near_lng": uni_info["lng"] if uni_info else None,
            "near_distance_km": distance_km if uni_info else None,
            # P0 硬约束补充
            "female_only": filters.get("female_only") or extracted.get("female_only"),
        }

        # 3. 搜索 unit_types（主搜索表）+ JOIN institutes + 聚合 rooms 库存
        unit_results = await self.property_service.search_unit_types(
            district=district,
            price_min=Decimal(str(price_min)) if price_min else None,
            price_max=Decimal(str(price_max)) if price_max else None,
            bedrooms=bedrooms,
            near_lat=merged_filters["near_lat"],
            near_lng=merged_filters["near_lng"],
            near_distance_km=merged_filters["near_distance_km"],
            female_only=merged_filters.get("female_only"),
            limit=500,
        )

        # 4. Embedding 语义排序（用 unit_types.embedding）
        embedding_scores: dict[int, float] = {}
        if unit_results:
            try:
                from app.services.embedding_service import EmbeddingService
                import json as _json; _np = __import__("numpy")
                emb_svc = EmbeddingService()
                query_vec = await emb_svc.generate_embedding(message)
                if query_vec is not None:
                    for ut in unit_results:
                        emb_str = ut.get("embedding")
                        if emb_str:
                            try:
                                ut_vec = _json.loads(emb_str)
                                cos = float(_np.dot(query_vec, ut_vec) / (_np.linalg.norm(query_vec) * _np.linalg.norm(ut_vec)))
                                embedding_scores[ut["unit_type"].id] = max(0, cos)
                            except Exception:
                                embedding_scores[ut["unit_type"].id] = 0.5
                    logger.info("Embedding: %d/%d unit_types scored", len(embedding_scores), len(unit_results))
                else:
                    for ut in unit_results: embedding_scores[ut["unit_type"].id] = 0.5
            except Exception:
                logger.warning("Embedding 不可用")
                for ut in unit_results: embedding_scores[ut["unit_type"].id] = 0.5

        # 5. LLM 推荐回复（结构化数据 → 模板回复）
        source_info = f"\n\n---\n[检索] 共 {len(unit_results)} 种户型"
        if llm.is_available and unit_results:
            try:
                top_n = min(3, len(unit_results))
                hard_filters = extracted.get("hard_filters", [])
                soft_prefs = extracted.get("soft_preferences", [])
                p2 = extracted.get("p2_highlights", [])
                school = (extracted.get("institution") or filters.get("institution") or "")
                school_name = uni_info["name"] if uni_info else school

                # 构建结构化上下文
                ctx = {
                    "query": message,
                    "school": school_name,
                    "currency": target_currency,
                    "total": len(unit_results),
                    "top_n": top_n,
                    "p0": {
                        "district": district or "不限",
                        "price_max": price_max,
                        "price_min": price_min,
                        "bedrooms": bedrooms,
                        "property_type": property_type,
                        "female_only": merged_filters.get("female_only"),
                        "min_lease_months": min_lease_months,
                        "hard_filters": hard_filters,
                    },
                    "p1": {"soft_preferences": soft_prefs},
                    "p2": {"highlights": p2},
                    "candidates": [],
                }

                for i, ut in enumerate(unit_results[:top_n], 1):
                    inst = ut["institute"]
                    t = ut["unit_type"]
                    sym = get_symbol(getattr(t, 'currency', None))
                    district = inst.district or ""

                    # 通勤数据：查表 → room_commutes → '暂无'
                    tbl = _lookup_commute(school, district)
                    if tbl:
                        commute_data = {"walk_min": tbl[0], "transit_min": tbl[1], "source": "lookup_table"}
                    elif uni_info:
                        try:
                            from app.models.room_commute import RoomCommute
                            from app.models.property import Room, RoomStatus
                            sub_stmt = (
                                select(RoomCommute).join(Room, RoomCommute.room_id == Room.id)
                                .where(Room.unit_type_id == t.id, RoomCommute.university_id == uni_info["id"])
                                .limit(1)
                            )
                            rc = (await self.session.execute(sub_stmt)).scalar_one_or_none()
                            if rc:
                                commute_data = {"walk_min": rc.walk_min, "transit_min": rc.transit_min, "source": rc.source}
                        except Exception:
                            pass
                    if not commute_data:
                        commute_data = {"walk_min": None, "transit_min": None, "source": "unknown"}

                    candidate = {
                        "rank": i,
                        "id": t.id,
                        "name": t.name,
                        "institute": inst.name or "",
                        "district": district,
                        "price": float(t.base_rent),
                        "symbol": sym,
                        "bedrooms": t.bedrooms,
                        "bathrooms": t.bathrooms,
                        "area_sqm": float(t.area_sqm) if t.area_sqm else None,
                        "available_rooms": ut["available_rooms"],
                        "institute_amenities": inst.amenities or [],
                        "unit_amenities": t.amenities or [],
                        "description": (inst.description or "")[:200],
                        "special_offer": t.special_offer or "",
                        "commute": commute_data,
                        "safety_score": None,  # 后续从 property_pois 取
                        "embedding_score": embedding_scores.get(t.id, 0.5),
                    }
                    ctx["candidates"].append(candidate)

                user_prompt = json.dumps(ctx, ensure_ascii=False, indent=2)
                result = await llm.complete_json(RECOMMEND_SYSTEM_PROMPT, user_prompt, max_tokens=1500)
                reply = str(result.get("reply") or f"为您找到 {len(unit_results)} 种户型。") + source_info
            except Exception:
                logger.exception("LLM 推荐生成失败")
                reply = f"为您找到 {len(unit_results)} 种户型。{AI_UNAVAILABLE_HINT}{source_info}"
        elif not llm.is_available:
            reply = f"为您找到 {len(unit_results)} 种户型。{AI_UNAVAILABLE_HINT}{source_info}"
        else:
            reply = f"为您找到 {len(unit_results)} 种户型。尝试放宽条件或换个区域试试？{source_info}"

        top_picks = [{"property_id": ut["unit_type"].id, "match_reason": f"{ut['institute'].name} | {ut['unit_type'].bedrooms}室 | ¥{float(ut['unit_type'].base_rent):.0f}/月 | {ut['available_rooms']}间可租", "pros": [], "cons": [], "property": ut["unit_type"]} for ut in unit_results[:3]]
        all_recs = [{"property_id": ut["unit_type"].id, "match_reason": "", "pros": [], "cons": [], "property": ut["unit_type"]} for ut in unit_results]

        return {
            "reply": reply, "recommendations": all_recs, "ai_available": llm.is_available,
            "extracted_filters": extracted, "top_picks": top_picks,
            "score_gap": None, "relaxation_level": 0,
            "candidate_snapshot": [ut["unit_type"].id for ut in unit_results], "source_info": source_info,
        }

    # ── 辅助方法 ──────────────────────────────────────────────────

    async def _lookup_institution(self, name: str) -> dict[str, Any] | None:
        """模糊查找学校 → {id, name, lat, lng}。

        匹配优先级：exact abbreviation → ILIKE name/cn → aliases 任意匹配 → ILIKE abbreviation
        查 universities 表（学校坐标），非 institutes（公寓机构）。
        """
        if not name or not name.strip():
            return None
        name = name.strip()
        from app.models.university import University

        # 1. 精确 abbreviation（NUS, UCL, LSE）
        stmt = select(University).where(func.lower(University.abbreviation) == name.lower())
        result = await self.session.scalars(stmt)
        uni = result.first()
        if uni:
            return {"id": uni.id, "name": uni.name_cn or uni.name, "lat": float(uni.latitude), "lng": float(uni.longitude), "country": uni.country, "city": uni.city}

        # 2. ILIKE name 或 name_cn
        pattern = f"%{name}%"
        stmt = select(University).where(
            ((func.lower(University.name).ilike(pattern)) | (func.lower(func.coalesce(University.name_cn, "")).ilike(pattern)))
        )
        result = await self.session.scalars(stmt)
        uni = result.first()
        if uni:
            return {"id": uni.id, "name": uni.name_cn or uni.name, "lat": float(uni.latitude), "lng": float(uni.longitude), "country": uni.country, "city": uni.city}

        # 3. aliases 数组包含
        stmt = select(University).where(University.aliases.any(name.lower()))
        result = await self.session.scalars(stmt)
        uni = result.first()
        if uni:
            return {"id": uni.id, "name": uni.name_cn or uni.name, "lat": float(uni.latitude), "lng": float(uni.longitude), "country": uni.country, "city": uni.city}

        # 4. ILIKE abbreviation
        stmt = select(University).where(func.lower(University.abbreviation).ilike(pattern))
        result = await self.session.scalars(stmt)
        uni = result.first()
        if uni:
            return {"id": uni.id, "name": uni.name_cn or uni.name, "lat": float(uni.latitude), "lng": float(uni.longitude), "country": uni.country, "city": uni.city}

        return None

    @staticmethod
    def _build_search_kwargs(filters: dict, limit: int = 500) -> dict[str, Any]:
        """将 Agent filters 转为 PropertyService.search() 参数。"""
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
        # 大学距离约束（P0）
        if filters.get("near_lat") is not None:
            kwargs["near_lat"] = filters["near_lat"]
            kwargs["near_lng"] = filters["near_lng"]
            kwargs["near_distance_km"] = filters["near_distance_km"]
        if filters.get("female_only") is not None:
            kwargs["female_only"] = filters["female_only"]
        amenities = filters.get("amenities")
        if amenities and isinstance(amenities, list) and len(amenities) > 0:
            kwargs["amenities"] = amenities
        for k in ("room_type", "bathrooms", "area_min", "area_max", "min_lease_months", "max_lease_months", "available_from"):
            v = filters.get(k)
            if v is not None and v != "":
                kwargs[k] = float(v) if k in ("area_min", "area_max") else (int(v) if k in ("bathrooms", "min_lease_months", "max_lease_months") else str(v))
        return kwargs

    @staticmethod
    def _build_source_info(result_count: int, filters: dict[str, Any], relaxation_level: int, relaxed_fields: list[str]) -> str:
        """生成检索溯源信息。"""
        parts = [f"\n\n---\n[检索] 本次基于 {result_count} 套房源检索"]
        filter_parts = []
        for key, label in {"district": "区域", "price_min": "最低预算", "price_max": "最高预算",
                            "bedrooms": "户型", "property_type": "类型"}.items():
            val = filters.get(key)
            if val is not None and val != "":
                if key in ("price_min", "price_max"):
                    val = f"¥{int(val):,}"
                elif key == "property_type":
                    val = {"studio": "单间", "1-bed": "一室", "2-bed": "两室+", "shared": "合租", "house": "别墅"}.get(str(val), str(val))
                filter_parts.append(f"{label}: {val}")
        if filter_parts:
            parts.append("条件: " + " | ".join(filter_parts))
        if relaxation_level > 0 and relaxed_fields:
            parts.append(f"已放宽: {' → '.join(relaxed_fields)}")
        return "\n".join(parts)

    @staticmethod
    def validate_recommendations(recommendations: list[dict], candidate_snapshot: list[int]) -> tuple[list[dict], int]:
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
        return valid, dropped

    # ── ReAct Tool Loop 模式（复杂查询：通勤/POI/模糊条件） ────

    SEARCH_REACT_PROMPT = """你是面向留学生的海外租房搜索专家。按需使用工具，不要全部调用。

可用工具：
- extract_filters: 从自然语言提取筛选条件（district/price/bedrooms/amenities）
- property_search: 搜索房源（支持 query + 结构化条件，自动渐进放宽）
- score_properties: 对搜索结果质量评分（传入 candidate_ids）
- gap_detect: 检测分数断层
- safe_fallback_check: 检查检索质量
- query_rewrite: 改写模糊查询为精确条件
- poi_lookup: 查询房源周边设施（超市/地铁/餐厅）
- commute_calc: 计算通勤时间

流程建议（不要死板遵循，按实际情况灵活调整）：
1. extract_filters → 提取条件
2. property_search → 搜索（可同时传 query 和 filters）
3. 如果用户提到通勤 → commute_calc
4. 如果用户问周边 → poi_lookup
5. score_properties → 评分
6. 用中文输出推荐回复（先总结数量，再逐套介绍亮点）

关键规则：
- 最多调用 4 个工具，之后必须输出中文回复
- 只推荐真实房源，不编造
- 结果少时诚实告知+给放宽建议
- 口语化中文，像朋友在给建议"""

    async def search_react(self, message: str, filters: dict[str, Any] | None = None) -> AgentResult:
        """ReAct Tool Loop 搜索：LLM 自主决定工具调用顺序。

        适用场景：涉及通勤计算、POI 查询、条件模糊需要改写等复杂查询。
        简单条件查询仍走 search() 快速路径。
        """
        return await self.handle_with_react(
            context=AgentContext(
                user_message=message,
                filters=filters,
            ),
            system_prompt=self.SEARCH_REACT_PROMPT,
            max_iterations=5,
        )

    # ── Agent 接口 ────────────────────────────────────────────────

    async def handle(self, context: AgentContext) -> AgentResult:
        """搜索入口：根据查询复杂度自动选择快速路径或 ReAct 模式。

        简单条件（district + price）→ search() 快速管线
        复杂条件（含通勤/POI/模糊查询）→ search_react() Tool Loop
        """
        try:
            msg = context.user_message.lower()
            is_complex = any(kw in msg for kw in [
                "通勤", "多远", "多久", "地铁站", "公交", "走路", "骑车", "开车",
                "附近有", "周边", "超市", "餐馆", "健身房",
                "便宜点", "贵一点", "少一点", "多一点",
            ])

            if is_complex:
                react_result = await self.search_react(
                    message=context.user_message,
                    filters=context.filters,
                )
                return react_result

            result = await self.search(
                message=context.user_message,
                filters=context.filters,
            )
            return AgentResult(
                content=result.get("reply", ""),
                success=True,
                data=result,
            )
        except Exception as exc:
            logger.exception("SearchAgent 失败")
            return AgentResult(
                content="",
                success=False,
                error=AgentError(
                    type_=AgentErrorType.EXTERNAL_API_FAILURE,
                    message=str(exc),
                    agent_id="search_agent",
                ),
            )

"""搜索 Agent —— 确定性搜索管线（召回 → 约束检查 → 消融放宽 → 多信号重排 → LLM 生成）

HEAD 适配：两层模型 (Institute → UnitType)，无 legacy Room 兼容路径。
"""
from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Any


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
    from app.services.embedding_service import get_embedding_service

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
        emb_svc = get_embedding_service()
        vec = await emb_svc.generate_embedding(text)
        if vec is None:
            return None
        # embedding 列现为 pgvector Vector(1536)，直接存 list[float]，不再 json.dumps
        ut.embedding = vec
        await session.commit()
        logger.info("UnitType #%s embedding generated (%d chars)", unit_type_id, len(text))
        return text
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
    "苏州": "CNY", "园区": "CNY", "SIP": "CNY",
}
_COUNTRY_CURRENCY: dict[str, str] = {
    "GB": "GBP", "SG": "SGD", "US": "USD", "HK": "HKD", "CN": "CNY",
    "UK": "GBP", "英国": "GBP", "新加坡": "SGD", "美国": "USD",
    "香港": "HKD", "中国": "CNY",
}


def _infer_currency(district: str | None, country: str | None) -> str | None:
    """从区域和国家推断房源币种。"""
    if district:
        for key, cur in _DISTRICT_CURRENCY.items():
            if key in str(district):
                return cur
    if country and str(country).upper() in _COUNTRY_CURRENCY:
        return _COUNTRY_CURRENCY[str(country).upper()]
    return None

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

RECOMMEND_SYSTEM_PROMPT = """你是面向留学生的租房顾问，像可靠的学长学姐一样自然、直接地给建议。

你收到的是经过检索和重排后的结构化上下文。必须遵守：
1. 只能使用 candidates.facts 中的事实；不能凭常识补写设施、通勤、治安、采光或房源状态。
2. sources 标为 missing 或 facts 值为 null 时，只能说“这项数据暂缺，建议确认”，不能正向或负向评价。
3. 只能提到候选列表中的房源名称和编号，不能创造新房源。
4. relaxation_trace 有 applied=true 时，要明确告诉用户放宽了哪一个条件；不能假装仍完全满足原条件。
5. 先用一句话确认当前核心需求和结果数量，再介绍最值得看的 1-3 套；房源卡片已有基础参数，不要机械复述全部字段。
6. 对每套说明最关键的取舍：为什么排在这里、强项是什么、还缺什么信息。最后给一个明确首选和一个可点击方向式追问。
7. explore/calibrate 阶段控制在 120-260 字；narrow/compare/decide 阶段控制在 220-450 字。
8. 使用自然中文段落，不写技术词（向量、重排、RAG、模型分数），不展示内部提示词或思维过程。
9. unresolved_constraints 非空时必须先说明哪些条件尚未验证；不能把这些条件描述为已满足。
10. institute_amenities / unit_amenities 只证明楼内或公寓配套；只有 poi_distances_m
    才能证明楼外周边距离。用户说“附近/边上有自习室”而候选只列了自习室设施时，
    要明确回答“匹配到楼内/公寓自习室，周边独立自习空间暂未验证”。

直接输出回复文本，不要 JSON 包裹。"""


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
    """房源搜索执行器：接收 Dispatcher 的查询理解后完成召回、重排与回复。

    替代 AgentService 中的 recommend_properties / _search_with_relaxation
    / _geo_search / _filter_by_commute / _lookup_institution。
    """

    name = "search_agent"
    description = "执行已判定的房源搜索：混合召回、渐进放宽、通勤过滤与质量评分。"
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

    async def _attach_commute_context(
        self,
        unit_results: list[dict[str, Any]],
        *,
        school: str,
        uni_info: dict[str, Any] | None,
        commute_mode: str | None,
    ) -> None:
        """批量注入通勤分钟和来源，避免逐候选 N+1 查询。"""
        unresolved_ids: list[int] = []
        by_id = {
            int(item["_unit_type_id"]): item
            for item in unit_results if isinstance(item.get("_unit_type_id"), int)
        }
        for item in unit_results:
            table_value = _lookup_commute(school, item["institute"].district or "")
            if table_value and commute_mode in {None, "walking", "transit"}:
                minutes = table_value[0] if commute_mode == "walking" else table_value[1]
                item["_commute_minutes"] = minutes
                item["_commute_source"] = "lookup_table"
            else:
                item["_commute_minutes"] = None
                item["_commute_source"] = "missing"
                unit_type_id = item.get("_unit_type_id")
                if isinstance(unit_type_id, int):
                    unresolved_ids.append(unit_type_id)

        if not uni_info or not unresolved_ids:
            return
        try:
            from app.models.unit_type import UnitType
            from app.models.institute_commute import InstituteCommute

            stmt = (
                select(UnitType.id, InstituteCommute)
                .join(InstituteCommute, InstituteCommute.institute_id == UnitType.institute_id)
                .where(
                    UnitType.id.in_(unresolved_ids),
                    InstituteCommute.university_id == uni_info["id"],
                )
            )
            rows = (await self.session.execute(stmt)).all()
            for unit_type_id, commute in rows:
                item = by_id.get(int(unit_type_id)) if unit_type_id is not None else None
                if item is None or item.get("_commute_minutes") is not None:
                    continue
                if commute_mode == "walking":
                    minutes = commute.walk_min
                elif commute_mode == "driving":
                    minutes = commute.drive_min
                elif commute_mode in {None, "transit"}:
                    minutes = commute.transit_min
                else:
                    minutes = None
                if isinstance(minutes, (int, float)):
                    item["_commute_minutes"] = minutes
                    item["_commute_source"] = commute.source or "room_commutes"
        except Exception:
            logger.warning("批量加载通勤数据失败，保留 missing 标记", exc_info=True)

    @staticmethod
    def _merge_recall_legs(*legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """合并语义召回与结构化召回，按户型去重并保留语义分。"""
        merged: dict[tuple[str, int], dict[str, Any]] = {}
        for leg in legs:
            for item in leg:
                unit_type_id = item.get("_unit_type_id")
                property_id = item.get("_property_id")
                if isinstance(unit_type_id, int):
                    key = ("unit_type", unit_type_id)
                elif isinstance(property_id, int):
                    key = ("property", property_id)
                else:
                    continue
                existing = merged.get(key)
                if existing is None:
                    merged[key] = item
                elif existing.get("embedding_score") is None and item.get("embedding_score") is not None:
                    existing["embedding_score"] = item["embedding_score"]
        return list(merged.values())

    async def _pipeline(
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        *,
        understanding: Any | None = None,
        stage: str = "narrow",
    ) -> dict[str, Any]:
        """执行已由 Dispatcher 判定的搜索任务，不在 Agent 内重复判断场景。"""
        from app.core.config import get_settings
        from app.services.agentic.context import pack_grounded_candidates, user_facing_sources
        from app.services.agentic.guided_search import (
            attach_poi_distances,
            build_guided_options,
            load_unit_type_poi,
            rank_by_poi,
        )
        from app.services.agentic.memory import merge_dialogue_filters
        from app.services.agentic.query_understanding import QueryUnderstanding
        from app.services.agentic.retrieval import (
            apply_constraint_ablation,
            build_relaxation_options,
            build_source_manifest,
            candidate_matches_filters,
            recommendation_explanation,
            rerank_candidates,
        )
        from app.services.compare_scoring import normalize_poi_requirements
        from app.services.embedding_service import get_embedding_service

        started_at = time.perf_counter()
        t_last = started_at
        def _lap(label: str) -> float:
            nonlocal t_last
            now = time.perf_counter()
            elapsed = (now - t_last) * 1000
            total = (now - started_at) * 1000
            logger.info("[TIMING] %s: %.0fms (total %.0fms)", label, elapsed, total)
            t_last = now
            return elapsed

        settings = get_settings()
        base_filters = dict(filters or {})
        if understanding is None:
            raise ValueError(
                "SearchAgent 缺少 Dispatcher 生成的 query understanding；"
                "请通过 Dispatcher 分发搜索任务"
            )
        if isinstance(understanding, dict):
            allowed = QueryUnderstanding.__dataclass_fields__.keys()
            understanding = QueryUnderstanding(**{
                key: value for key, value in understanding.items() if key in allowed
            })
        if not isinstance(understanding, QueryUnderstanding):
            raise TypeError("query understanding 类型无效")

        active_filters = merge_dialogue_filters(
            message=message,
            previous=base_filters,
            memory_filters={},
            extracted=understanding.extracted_filters,
            request_filters=None,
            remove_fields=understanding.remove_fields,
            remove_values=understanding.remove_values,
        )

        district = active_filters.get("district")
        if isinstance(district, str) and district.lower().strip() in _EN_TO_CN_CITY:
            district = _EN_TO_CN_CITY[district.lower().strip()]
            active_filters["district"] = district
        institution_name = active_filters.get("institution")
        commute_mode = active_filters.get("commute_mode")
        commute_minutes = active_filters.get("commute_minutes")
        if commute_minutes is not None:
            try:
                active_filters["commute_minutes"] = int(commute_minutes)
            except (TypeError, ValueError):
                active_filters.pop("commute_minutes", None)

        # 学校坐标仅在左侧未确定位置时才查询；如果 context_filters 已有
        # country + district，说明主搜索页已经完成了地理定位，无需重复。
        uni_info: dict[str, Any] | None = None
        distance_km = 20.0
        if institution_name:
            try:
                async with self.session.begin_nested():
                    uni_info = await self._lookup_institution(str(institution_name))
                if uni_info and commute_mode in _COMMUTE_PRE_FILTER_KM:
                    distance_km = _COMMUTE_PRE_FILTER_KM[str(commute_mode)]
            except Exception:
                logger.warning("大学坐标解析失败: %s", institution_name, exc_info=True)
        if uni_info and not district:
            city = str(uni_info.get("city") or "").strip()
            district = _EN_TO_CN_CITY.get(city.lower(), city) or None
            if district:
                active_filters["district"] = district
        if uni_info and not active_filters.get("country") and uni_info.get("country"):
            active_filters["country"] = str(uni_info["country"])

        market_currency = _infer_currency(district, active_filters.get("country"))
        requested_currency = active_filters.get("currency")
        target_currency = str(market_currency or requested_currency or "")
        if target_currency:
            active_filters["currency"] = target_currency
            for price_field in ("price_min", "price_max"):
                value = active_filters.get(price_field)
                if value is not None:
                    active_filters[price_field] = resolve_search_price(
                        message, float(value), target_currency
                    )
        unresolved_constraints: list[str] = []
        if institution_name and not uni_info:
            unresolved_constraints.append(
                f"未能定位学校“{institution_name}”，学校距离与通勤尚未验证"
            )
        requires_school_clarification = bool(
            institution_name and not uni_info and not district
        )

        semantic_query = understanding.embedding_text(message)
        _lap("filter_merge+uni_lookup")
        query_vec: list[float] | None = None
        embedding_service = get_embedding_service()
        if embedding_service.is_available:
            try:
                query_vec = await embedding_service.generate_embedding(semantic_query)
                _lap("embedding")
            except Exception:
                logger.warning("Query Rewrite 向量化失败，降级到结构化+词面检索")

        pool_limit = max(30, min(int(settings.agent_retrieval_pool_size), 300))
        leg_limit = pool_limit if query_vec is None else max(15, pool_limit // 2)
        common_search = {
            "country": active_filters.get("country"),
            "near_lat": uni_info["lat"] if uni_info else None,
            "near_lng": uni_info["lng"] if uni_info else None,
            "near_distance_km": distance_km if uni_info else None,
            "female_only": active_filters.get("female_only"),
            "limit": leg_limit,
        }
        strict_semantic: list[dict[str, Any]] = []
        if not requires_school_clarification:
            strict_semantic = await self.property_service.search_unit_types(
                district=district,
                price_min=(Decimal(str(active_filters["price_min"])) if active_filters.get("price_min") is not None else None),
                price_max=(Decimal(str(active_filters["price_max"])) if active_filters.get("price_max") is not None else None),
                bedrooms=active_filters.get("bedrooms"),
                property_type=active_filters.get("property_type") or active_filters.get("room_type"),
                query_vec=query_vec,
                **common_search,
            )
        strict_structured: list[dict[str, Any]] = []
        if query_vec is not None and not requires_school_clarification:
            strict_structured = await self.property_service.search_unit_types(
                district=district,
                price_min=(Decimal(str(active_filters["price_min"])) if active_filters.get("price_min") is not None else None),
                price_max=(Decimal(str(active_filters["price_max"])) if active_filters.get("price_max") is not None else None),
                bedrooms=active_filters.get("bedrooms"),
                property_type=active_filters.get("property_type") or active_filters.get("room_type"),
                query_vec=None,
                **common_search,
            )
        strict_recall = self._merge_recall_legs(strict_semantic, strict_structured)
        _lap(f"db_search (semantic={len(strict_semantic)} structured={len(strict_structured)})")

        await self._attach_commute_context(
            strict_recall,
            school=str(institution_name or ""),
            uni_info=uni_info,
            commute_mode=str(commute_mode) if commute_mode else None,
        )
        strict_matches = [
            item for item in strict_recall
            if candidate_matches_filters(item, active_filters)
        ]
        logger.info(
            "管线调试: recall=%d strict=%d filters=%s",
            len(strict_recall), len(strict_matches),
            {k: v for k, v in active_filters.items() if v and k != "near_lat" and k != "near_lng"},
        )

        # 严格结果不足时只多查一次宽召回池；各约束消融都在内存中复用该池。
        recall_pool = list(strict_recall)
        if len(strict_matches) < int(settings.agent_min_results) and not requires_school_clarification:
            broad_semantic = await self.property_service.search_unit_types(
                district=None,
                price_min=None,
                price_max=None,
                bedrooms=None,
                property_type=None,
                query_vec=query_vec,
                **common_search,
            )
            broad_structured: list[dict[str, Any]] = []
            if query_vec is not None:
                broad_structured = await self.property_service.search_unit_types(
                    district=None,
                    price_min=None,
                    price_max=None,
                    bedrooms=None,
                    property_type=None,
                    query_vec=None,
                    **common_search,
                )
            broad_recall = self._merge_recall_legs(broad_semantic, broad_structured)
            known_ids = {int(item["unit_type"].id) for item in recall_pool}
            new_items = [
                item for item in broad_recall
                if int(item["unit_type"].id) not in known_ids
            ]
            await self._attach_commute_context(
                new_items,
                school=str(institution_name or ""),
                uni_info=uni_info,
                commute_mode=str(commute_mode) if commute_mode else None,
            )
            recall_pool.extend(new_items)

        _lap(f"commute+broad_recall (pool={len(recall_pool)})")
        raw_poi_requirements = active_filters.get("poi_requirements") or []
        poi_pref_keys = normalize_poi_requirements(raw_poi_requirements)
        poi_by_unit_type: dict[int, dict] = {}
        poi_unit_type_ids = [
            int(item["_unit_type_id"])
            for item in recall_pool if isinstance(item.get("_unit_type_id"), int)
        ]
        if poi_unit_type_ids:
            try:
                poi_by_unit_type = await load_unit_type_poi(
                    self.session,
                    poi_unit_type_ids,
                )
                attach_poi_distances(recall_pool, poi_by_unit_type)
                if poi_pref_keys:
                    # 此函数同时注入 POI 分；最终顺序仍由统一 reranker 决定。
                    rank_by_poi(recall_pool, poi_by_unit_type, poi_pref_keys)
            except Exception:
                logger.warning("POI 数据加载失败，降级为无 POI 信号重排", exc_info=True)

        _lap(f"poi_load (poi_unit_types={len(poi_by_unit_type)})")
        selected, effective_filters, relaxation_trace, relaxation_level = apply_constraint_ablation(
            recall_pool,
            active_filters,
            min_results=max(1, int(settings.agent_min_results)),
        )
        _lap(f"ablation (selected={len(selected)})")
        reranked = rerank_candidates(
            selected,
            query=semantic_query,
            filters=effective_filters,
        )
        _lap(f"rerank (reranked={len(reranked)})")

        # 按公寓去重：同一 institute 只保留得分最高的那条
        seen_institutes: set[int] = set()
        deduped: list[dict[str, Any]] = []
        for item in reranked:
            inst_id = item["institute"].id
            if inst_id not in seen_institutes:
                seen_institutes.add(inst_id)
                deduped.append(item)
        reranked = deduped

        source_manifest = build_source_manifest(reranked)
        school_name = str(uni_info["name"] if uni_info else institution_name or "")
        grounded_context = pack_grounded_candidates(
            query=understanding.rewritten_query or message,
            stage=stage,
            filters=effective_filters,
            candidates=reranked,
            school=school_name,
            currency=target_currency or "未指定",
            relaxation_trace=relaxation_trace,
            unresolved_constraints=unresolved_constraints,
            max_candidates=5 if stage in {"compare", "decide"} else 3,
            char_budget=int(settings.agent_context_char_budget),
        )

        guided_options = build_guided_options(
            active_filters={
                "poi_requirements": raw_poi_requirements,
                "price_max": effective_filters.get("price_max"),
                "bathrooms": effective_filters.get("bathrooms"),
            },
            poi_by_ut=poi_by_unit_type,
            result_count=len(reranked),
        )
        relaxation_options = build_relaxation_options(relaxation_trace)
        if len(reranked) < int(settings.agent_min_results):
            guided_options = [*relaxation_options, *guided_options][:5]

        def _recommendation(item: dict[str, Any]) -> dict[str, Any]:
            reason, pros, cons = recommendation_explanation(item, effective_filters)
            applied_relaxation = next(
                (
                    str(trace.get("action"))
                    for trace in relaxation_trace
                    if trace.get("applied") and trace.get("action")
                ),
                None,
            )
            if applied_relaxation:
                cons = [f"已放宽：{applied_relaxation}", *cons][:2]
            return {
                "property_id": int(item.get("_property_id", item["unit_type"].id)),
                "rank": int(item.get("_rank", 0)),
                "final_score": float(item.get("_final_score", 0.0)),
                "score_breakdown": dict(item.get("_score_breakdown") or {}),
                "match_reason": reason,
                "pros": pros,
                "cons": cons,
                "property": item.get("response_property") or item["unit_type"],
                "poi_distances": item.get("_poi_distances") or {},
                "source_metadata": dict(item.get("_source_metadata") or {}),
            }

        all_recommendations = [_recommendation(item) for item in reranked]
        scores = [float(item.get("_final_score", 0.0)) / 100.0 for item in reranked]
        score_gap = detect_score_gap(scores)
        source_info = (
            f"\n\n数据依据：房源资料、库存"
            f"{'、通勤' if any(item.get('_commute_source') != 'missing' for item in reranked) else ''}"
            f"{'、周边设施' if any(item.get('_poi_distances') for item in reranked) else ''}。"
        ) if reranked else ""

        return {
            "unit_results": reranked,
            "extracted": understanding.extracted_filters,
            "explicit_filters": understanding.extracted_filters,
            "effective_filters": effective_filters,
            "understanding": understanding,
            "ctx": grounded_context,
            "school_name": school_name,
            "source_info": source_info,
            "source_manifest": source_manifest,
            "unresolved_constraints": unresolved_constraints,
            "sources": user_facing_sources(source_manifest),
            "guided_options": guided_options,
            "top_picks": all_recommendations[:3],
            "all_recs": all_recommendations,
            "score_gap": score_gap,
            "relaxation_level": relaxation_level,
            "relaxation_trace": relaxation_trace,
            "candidate_snapshot": [
                int(item.get("_property_id", item["unit_type"].id))
                for item in reranked
            ],
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
        }

    # ── 回复生成（非流式 / 真流式 共用） ─────────────────────────

    @staticmethod
    def _reply_messages(prep: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": RECOMMEND_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prep["ctx"], ensure_ascii=False, indent=2)},
        ]

    def _fallback_reply(self, prep: dict[str, Any]) -> str:
        """LLM 不可用 / 失败 / 空回复时的规则兜底。"""
        unit_results = prep["unit_results"]
        unresolved = prep.get("unresolved_constraints") or []
        if not unit_results and unresolved:
            return f"{unresolved[0]}。请补充学校全称或所在城市，我再继续筛选。"
        if not unit_results:
            traces = [
                trace for trace in prep.get("relaxation_trace", [])
                if int(trace.get("after_count", 0)) > 0
            ]
            if traces:
                best = max(traces, key=lambda item: int(item.get("after_count", 0)))
                return (
                    "按当前全部条件暂时没有匹配户型。"
                    f"主要可以尝试：{best.get('action')}，预计能看到约 {best.get('after_count')} 套。"
                )
            return "按当前全部条件暂时没有匹配户型。可以先放宽预算、区域或户型中的一项。"
        if not get_llm_service().is_available:
            return f"为您找到 {len(unit_results)} 种户型。{AI_UNAVAILABLE_HINT}"
        # LLM 失败：列出 top 5 结果的关键信息
        school = prep["school_name"]
        lines = [f"为您找到 {len(unit_results)} 种户型（AI 暂不可用，以下是筛选结果摘要）：", ""]
        for i, ut in enumerate(unit_results[:5], 1):
            t = ut["unit_type"]; inst = ut["institute"]
            sym = get_symbol(getattr(t, 'currency', None))
            commute = _lookup_commute(school, inst.district or "")
            commute_str = f" | 到{school}: 步行{commute[0]}分钟/公交{commute[1]}分钟" if commute else ""
            lines.append(f"{i}. {t.name} — {sym}{float(t.base_rent):.0f}/月 | {t.bedrooms}室{t.bathrooms}卫 | {inst.district}{commute_str}")
        if len(unit_results) > 5:
            lines.append(f"...还有 {len(unit_results)-5} 种")
        return "\n".join(lines)

    async def _gen_reply(self, prep: dict[str, Any]) -> str:
        """非流式 LLM 回复；失败降级为规则摘要。"""
        from app.core.config import get_settings

        llm = get_llm_service()
        if llm.is_available and prep["unit_results"]:
            try:
                reply = (await llm.complete_text(
                    messages=self._reply_messages(prep),
                    temperature=float(get_settings().agent_recommend_temperature),
                    max_tokens=1200,
                ) or "").strip()
                if len(reply) < 20:
                    raise ValueError("LLM 返回空回复")
                return reply + prep["source_info"]
            except Exception as _e:
                logger.exception("LLM 推荐生成失败，降级为规则摘要: %s", _e)
        return self._fallback_reply(prep) + prep["source_info"]

    @staticmethod
    def _assemble(prep: dict[str, Any], reply: str) -> dict[str, Any]:
        return {
            "reply": reply, "recommendations": prep["all_recs"],
            "ai_available": get_llm_service().is_available,
            "extracted_filters": prep["extracted"], "top_picks": prep["top_picks"],
            "effective_filters": prep["effective_filters"],
            "explicit_filters": prep["explicit_filters"],
            "rewritten_query": prep["understanding"].rewritten_query,
            "score_gap": prep["score_gap"],
            "relaxation_level": prep["relaxation_level"],
            "relaxation_trace": prep["relaxation_trace"],
            "candidate_snapshot": prep["candidate_snapshot"], "source_info": prep["source_info"],
            "guided_options": prep["guided_options"],
            "source_manifest": prep["source_manifest"],
            "sources": prep["sources"],
            "latency_ms": prep["latency_ms"],
            "unit_results": prep["unit_results"],
        }

    async def search(
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        *,
        understanding: Any | None = None,
        stage: str = "narrow",
    ) -> dict[str, Any]:
        """检索 + LLM 推荐（非流式，供 /messages 端点与 Agent handle 使用）。"""
        prep = await self._pipeline(
            message, filters, understanding=understanding, stage=stage
        )
        reply = await self._gen_reply(prep)
        return self._assemble(prep, reply)

    async def search_stream(
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        *,
        understanding: Any | None = None,
        stage: str = "narrow",
    ):
        """真流式检索：LLM 逐 token yield，最后一条 meta 携带卡片数据 + 引导选项。

        yield 事件：
        - {"type": "token", "text": 回复文本增量}
        - {"type": "meta", "reply": 完整回复, "recommendations": [...],
           "top_picks": [...], "guided_options": [...]}
        """
        from app.core.config import get_settings

        prep = await self._pipeline(
            message, filters, understanding=understanding, stage=stage
        )
        llm = get_llm_service()
        reply = ""
        stream_failed = False
        if llm.is_available and prep["unit_results"]:
            try:
                msg = self._reply_messages(prep)
                async for tok in llm.complete_text_stream(
                    msg,
                    temperature=float(get_settings().agent_recommend_temperature),
                    max_tokens=1200,
                ):
                    reply += tok
                    yield {"type": "token", "text": tok}
            except Exception as e:
                stream_failed = True
                # 避免 logger.exception 因 Windows GBK 编码再次抛异常
                logger.error("LLM 流式推荐失败: type=%s msg=%s", type(e).__name__, str(e)[:200])
                # 已经 yield 给客户端的 token 无法撤回，必须保留在完整回复中，
                # 否则界面展示文本会与历史持久化内容不一致。
        if len(reply.strip()) < 20:
            fallback = self._fallback_reply(prep)
            continuation = f"\n\n{fallback}" if reply else fallback
            reply += continuation
            yield {"type": "token", "text": continuation}
        source_info = prep["source_info"]
        if source_info:
            reply += source_info
            yield {"type": "token", "text": source_info}
        yield {
            "type": "meta",
            "reply": reply,
            "recommendations": prep["all_recs"],
            "top_picks": prep["top_picks"],
            "guided_options": prep["guided_options"],
            "effective_filters": prep["effective_filters"],
            "explicit_filters": prep["explicit_filters"],
            "rewritten_query": prep["understanding"].rewritten_query,
            "score_gap": prep["score_gap"],
            "relaxation_level": prep["relaxation_level"],
            "relaxation_trace": prep["relaxation_trace"],
            "candidate_snapshot": prep["candidate_snapshot"],
            "source_manifest": prep["source_manifest"],
            "sources": prep["sources"],
            "ai_available": llm.is_available and not stream_failed,
            "latency_ms": prep["latency_ms"],
            "unit_results": prep["unit_results"],
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

        # 高频学校保留确定性坐标兜底，避免学校表尚未初始化时整轮请求失败。
        known_locations = {
            "NUS": {"id": None, "name": "新加坡国立大学", "lat": 1.2966, "lng": 103.7764, "country": "SG", "city": "Singapore"},
            "NTU": {"id": None, "name": "南洋理工大学", "lat": 1.3483, "lng": 103.6831, "country": "SG", "city": "Singapore"},
            "UCLA": {"id": None, "name": "加州大学洛杉矶分校", "lat": 34.0689, "lng": -118.4452, "country": "US", "city": "Los Angeles"},
        }
        fallback = known_locations.get(name.upper())
        if fallback:
            return fallback

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

    # ── Agent 接口 ────────────────────────────────────────────────

    async def handle(self, context: AgentContext) -> AgentResult:
        """兼容编排器入口；场景选择由上游完成，本方法只执行确定性搜索。"""
        try:
            understanding = context.extra.get("query_understanding")
            result = await self.search(
                message=context.user_message,
                filters=context.filters,
                understanding=understanding,
                stage=str(context.extra.get("stage") or "narrow"),
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

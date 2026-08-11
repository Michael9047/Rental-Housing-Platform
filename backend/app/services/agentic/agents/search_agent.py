"""搜索 Agent —— 完整搜索管线（提取条件 → 检索+放宽 → 通勤过滤 → 评分 → LLM 推荐）

Phase 5: 从 AgentService 迁移全部搜索逻辑，独立于 AgentService。
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable, Collection
from decimal import Decimal
from typing import Any


def build_search_text(unit_type) -> str:
    """将 UnitType + Institute 两层信息拼接为 embedding 文本。"""
    institute = getattr(unit_type, "institute", None)
    parts = []
    if unit_type.name: parts.append(unit_type.name)
    if institute and institute.name: parts.append(institute.name)
    if institute and institute.district: parts.append(f"区域: {institute.district}")
    if institute and institute.city: parts.append(f"城市: {institute.city}")
    if institute and institute.country: parts.append(f"国家: {institute.country}")
    if unit_type.property_type: parts.append(str(unit_type.property_type))
    if unit_type.bedrooms: parts.append(f"{unit_type.bedrooms}室")
    if unit_type.bathrooms: parts.append(f"{unit_type.bathrooms}卫")
    if unit_type.area_sqm: parts.append(f"{unit_type.area_sqm}平米")
    amenities = [*(unit_type.amenities or []), *((institute.amenities or []) if institute else [])]
    if amenities: parts.append(f"配套: {'、'.join(dict.fromkeys(amenities))}")
    if unit_type.description: parts.append(unit_type.description[:300])
    sym = get_symbol(unit_type.currency)
    if unit_type.base_rent: parts.append(f"月租: {sym}{float(unit_type.base_rent):.0f}")
    return " | ".join(p for p in parts if p)


def _describe_neighborhood(institute: Any, unit_type: Any, safety_info: dict | None = None) -> str:
    """根据建筑类型 + 配套档次 + 安全评分，生成社区阶层描述。

    数据驱动，不硬编码区域名。
    """
    country = getattr(institute, 'country', 'SG')
    bld_amenities = getattr(institute, 'amenities', None) or []
    bld_type = (getattr(institute, 'building_type', '') or "").lower()
    safety_score = safety_info.get("safety_score") if safety_info else None

    # 建筑档次评分
    if "condo" in bld_type or "pbsa" in bld_type or "new_build" in bld_type:
        bld_tier = 3
        bld_label = "公寓" if country == "SG" else "学生公寓"
    elif "hdb" in bld_type:
        bld_tier = 1
        bld_label = "组屋"
    elif "hmo" in bld_type:
        bld_tier = 0
        bld_label = "合租房"
    else:
        bld_tier = 1
        bld_label = "住宅"

    # 配套档次
    has_pool = any(a in str(bld_amenities) for a in ["泳池", "pool"])
    has_gym = any(a in str(bld_amenities) for a in ["健身房", "gym"])
    has_security = any(a in str(bld_amenities) for a in ["24小时安保", "门禁系统", "24h"])
    amenity_tier = (1 if has_pool else 0) + (1 if has_gym else 0) + (1 if has_security else 0)

    # 综合社区画像
    if country == "GB":
        if bld_tier >= 3 and amenity_tier >= 2:
            if safety_score and safety_score >= 4:
                return "高端学生社区，配套完善，治安优秀"
            return "学生公寓社区，配套齐全"
        elif bld_tier >= 3:
            return "学生公寓社区"
        elif amenity_tier >= 2:
            return "成熟住宅社区，配套较好"
        elif safety_score is not None and safety_score < 2.5:
            return "普通居民区，治安一般"
        else:
            return "普通居民区，生活成本较低"
    else:
        if bld_tier >= 3 and amenity_tier >= 2:
            return "高端公寓社区，泳池健身房俱全，居民以中高收入人群为主"
        elif bld_tier >= 3:
            return "公寓社区，配套完善"
        elif bld_tier == 1 and amenity_tier <= 1:
            if safety_score and safety_score < 2.5:
                return "普通组屋区，生活成本低"
            return "成熟组屋社区，周边配套完善，居民以本地家庭为主"
        else:
            return "普通住宅区"


def _describe_safety(safety_data: dict | None = None) -> str:
    """从 safety_data 生成安全描述。"""
    if not safety_data:
        return ""
    score = safety_data.get("safety_score")
    if score is None:
        return ""
    score = float(score)
    source = safety_data.get("data_source", "")
    if score >= 4.0:
        return "治安优秀" + ("（官方数据）" if source != "stub" else "")
    elif score >= 3.0:
        return "治安良好"
    elif score >= 2.0:
        return "治安一般"
    else:
        return "治安需注意"


def build_unit_type_search_text(
    institute: Any, unit_type: Any,
    poi_map: dict | None = None,
    commute_text: str | None = None,
    safety_data: dict | None = None,
) -> str:
    """RAG 富文本模板 — 自然语言描述，供 embedding 向量化。

    融合 Institute + UnitType + POI + Commute 四层信息，
    生成一段完整的房源描述，支持「找类似户型」「NUS附近带健身房空调studio」等语义检索。
    """
    parts = []

    # ── 公寓名 + 位置 ──
    name = institute.name_cn or institute.name or "公寓"
    district = institute.district or ""
    city = institute.city or ""
    country = "英国伦敦" if institute.country == "GB" else "新加坡"
    location = " ".join(p for p in [city, district] if p)
    parts.append(f"{name}位于{country} {location}".strip())

    # ── 户型 + 价格 ──
    ut_name = unit_type.name or ""
    bedrooms = f"{unit_type.bedrooms}室" if unit_type.bedrooms else ""
    bathrooms = f"{unit_type.bathrooms}卫" if unit_type.bathrooms else ""
    area = f"{float(unit_type.area_sqm):.0f}平米" if unit_type.area_sqm else ""
    currency_sym = "£" if getattr(institute, 'country', None) == "GB" else "S$"
    period = "周" if getattr(institute, 'country', None) == "GB" else "月"
    rent = f"{currency_sym}{float(unit_type.base_rent):.0f}/{period}" if unit_type.base_rent else ""
    parts.append(f"户型是{ut_name}，{bedrooms}{bathrooms}，{area}，租金{rent}")

    # ── 房内配套 ──
    ut_amenities = unit_type.amenities or []
    if ut_amenities:
        parts.append(f"房内配套：{'、'.join(ut_amenities)}")

    # ── 楼栋配套 ──
    bld_amenities = getattr(institute, 'amenities', None) or []
    if bld_amenities:
        parts.append(f"楼栋配套：{'、'.join(bld_amenities)}")

    # ── 社区阶层（数据驱动）──
    neighborhood = _describe_neighborhood(institute, unit_type, safety_info=safety_data)
    if neighborhood:
        parts.append(neighborhood)

    # ── 治安（真实评分）──
    safety = _describe_safety(safety_data)
    if safety:
        parts.append(safety)

    # ── 周边 POI（按数量和距离分档，自然语言描述） ──
    if poi_map:
        def _nearest_m(cat_keys: list[str]) -> int | None:
            best = None
            for k in cat_keys:
                for p in poi_map.get(k, []):
                    d = p.get("distance_m", 99999)
                    if best is None or d < best:
                        best = d
            return best

        # 距离描述词
        def _dist_word(d_m: int | None) -> str:
            if d_m is None or d_m > 1500:
                return "周边有"
            if d_m <= 300:
                return "楼下就是"
            if d_m <= 600:
                return "步行几分钟到"
            return "步行可达"

        def _count(cat_keys: list[str]) -> int:
            return sum(len(poi_map.get(k, [])) for k in cat_keys)

        # 交通
        n_tr = _count(["subway_station", "bus_station"])
        d_tr = _nearest_m(["subway_station", "bus_station"])
        w_tr = _dist_word(d_tr)
        if d_tr is not None and d_tr <= 300 and n_tr >= 2:
            parts.append(f"{w_tr}地铁站和公交站，出行很方便")
        elif n_tr >= 2:
            parts.append(f"{w_tr}地铁站，通勤方便")
        elif n_tr >= 1:
            parts.append(f"{w_tr}公交站")

        # 购物
        n_sh = _count(["supermarket", "mall", "market"])
        d_sh = _nearest_m(["supermarket", "mall", "market"])
        w_sh = _dist_word(d_sh)
        if n_sh >= 3:
            parts.append(f"{w_sh}超市和商场，日常购物方便")
        elif n_sh >= 1:
            parts.append(f"{w_sh}超市，满足日常采购")

        # 餐饮
        n_fd = _count(["restaurant", "cafe", "hawker_centre", "fast_food"])
        d_fd = _nearest_m(["restaurant", "hawker_centre", "fast_food"])
        w_fd = _dist_word(d_fd)
        if n_fd >= 6:
            parts.append(f"{w_fd}多家餐厅、食阁和咖啡厅，吃饭选择丰富")
        elif n_fd >= 3:
            parts.append(f"{w_fd}几家餐厅和食阁，解决吃饭没问题")
        elif n_fd >= 1:
            parts.append(f"{w_fd}餐厅和食阁")

        # 医院
        d_hp = _nearest_m(["hospital"])
        if d_hp is not None and d_hp <= 500:
            parts.append("紧邻医院，就医很方便")
        elif d_hp is not None and d_hp <= 1000:
            parts.append("步行可达医院")
        elif d_hp is not None and d_hp <= 3000:
            parts.append("周边有医院")

        # 药店
        n_ph = _count(["pharmacy"])
        d_ph = _nearest_m(["pharmacy"])
        w_ph = _dist_word(d_ph)
        if n_ph >= 2:
            parts.append(f"{w_ph}多家药店")
        elif n_ph >= 1:
            parts.append(f"{w_ph}药店")

        # 健身
        if _count(["gym"]) >= 1:
            parts.append("附近有健身房")

    # ── 通勤信息 ──
    if commute_text:
        parts.append(commute_text)

    # ── 公寓描述 ──
    desc = getattr(institute, 'description', None) or ""
    if desc:
        parts.append(desc[:200])

    return "。".join(p for p in parts if p) + "。"


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
from app.models.unit_type import UnitType, UnitTypeStatus
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
MAX_RECOMMENDATION_CARDS = 20

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
_COUNTRY_ALIASES: dict[str, str] = {
    "cn": "CN", "china": "CN", "中国": "CN", "中国大陆": "CN",
    "sg": "SG", "singapore": "SG", "新加坡": "SG", "新加坡市": "SG",
    "gb": "GB", "uk": "GB", "unitedkingdom": "GB", "英国": "GB",
    "us": "US", "usa": "US", "unitedstates": "US", "美国": "US",
    "au": "AU", "australia": "AU", "澳大利亚": "AU",
    "ca": "CA", "canada": "CA", "加拿大": "CA",
    "hk": "HK", "hongkong": "HK", "香港": "HK", "中国香港": "HK",
}
_SINGAPORE_SCOPE_ALIASES = frozenset({"sg", "singapore", "新加坡", "新加坡市"})

_FALLBACK_INSTITUTIONS = (
    "NUS", "NTU", "SMU", "SUTD", "UCL", "LSE", "KCL", "QMUL",
    "HKU", "CUHK", "HKUST", "UCLA", "USC",
)
_FALLBACK_INSTITUTION_PATTERN = re.compile(
    rf"\b({'|'.join(_FALLBACK_INSTITUTIONS)})\b",
    re.IGNORECASE,
)


def _normalize_country(value: Any) -> str | None:
    """把自然语言国家名标准化为数据库使用的两位代码。"""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    key = re.sub(r"[\s_-]+", "", raw).casefold()
    if key in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[key]
    return raw.upper() if len(raw) == 2 else raw


def _is_singapore_scope(value: Any) -> bool:
    """新加坡是国家/城市，不应作为 Institute.district 精确筛选。"""
    if value is None:
        return False
    return str(value).strip().casefold() in _SINGAPORE_SCOPE_ALIASES


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
→ {"country":"SG","city":"Singapore","district":null,"price_max":800,"currency":"SGD","institution":"NUS","hard_filters":["institution"],"soft_preferences":["price"],"p2_highlights":["精装修","泳池"]}

只输出 JSON。设施映射：独卫→独立卫浴, wifi→WiFi。currency：¥/人民币/元/块→CNY, £/英镑/镑→GBP, S$/新币→SGD。未提及时填 null。
新加坡/Singapore/SG 必须提取为 country="SG", city="Singapore", district=null；district 只填写杜佛、西海岸等国家内部区域。
注意：null 只表示本轮没有提及，绝不表示删除已有条件；清除条件由系统的独立协议处理。"""

RECOMMEND_SYSTEM_PROMPT = """你是留学生租房顾问。输入是结构化 JSON，只能使用其中的真实字段。

请用 180–320 字中文推荐 1–3 个候选户型，按实际候选数量使用以下短标记：
【结论】一句话概括最重要的选择差异。
【推荐1】公寓与户型名：租金、位置及最关键的 1–2 个亮点。
【推荐2】【推荐3】按实际候选数量继续，每项只写一句。
【怎么选】结合用户明确条件给出简短选择建议，并用一个短问题收尾。

规则：
1. 除指定短标记外，不输出 JSON、表格、项目符号或复杂 Markdown。
2. 不编造距离、通勤、设施、优惠、预算匹配或周边情况。
3. 字段缺失时直接略过，不逐项写“暂无数据”。
4. 通勤仅在分钟数非空时描述；source=lookup_table 时必须标注“估算”。
5. 只有所有候选的 currency 都非空且一致时，才能比较租金高低。
6. 不笼统声称“全部满足条件”，只点明数据可验证的匹配项。
7. 控制信息密度：每个推荐只保留最有区分度的事实，不复述全部字段。

直接输出带上述短标记的纯文本，不要 JSON 包裹。"""


_PROPERTY_TYPE_REASON_LABELS = {
    "studio": "Studio",
    "ensuite": "Ensuite",
    "1bed": "一室",
    "2bed": "两室",
    "3bed": "三室",
    "4bed": "四室",
    "5bed+": "五室及以上",
    "shared": "合租",
}


def _raw_value(value: Any) -> str:
    """读取枚举或字符串的原始值，供推荐理由安全展示。"""
    return str(getattr(value, "value", value) or "")


def _build_recommendation_reason(
    item: dict[str, Any],
    filters: dict[str, Any],
    *,
    school_name: str = "",
    commute: dict[str, Any] | None = None,
) -> str:
    """只用已验证字段拼接卡片推荐理由，最多保留六个事实。"""
    unit_type = item["unit_type"]
    institute = item["institute"]
    facts: list[str] = []

    location = str(
        getattr(institute, "district", None)
        or getattr(institute, "city", None)
        or ""
    ).strip()
    if location:
        facts.append(f"位于{location}")

    unit_currency = str(getattr(unit_type, "currency", "") or "").upper()
    target_currency = str(filters.get("currency") or "").upper()
    price = float(unit_type.base_rent)
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    currency_matches = bool(unit_currency and target_currency and unit_currency == target_currency)
    within_min = price_min is None or price >= float(price_min)
    within_max = price_max is None or price <= float(price_max)
    if currency_matches and (price_min is not None or price_max is not None) and within_min and within_max:
        facts.append("月租在预算内")

    property_type = _raw_value(getattr(unit_type, "property_type", None))
    type_label = _PROPERTY_TYPE_REASON_LABELS.get(property_type, property_type)
    specs = [type_label] if type_label else []
    area_sqm = getattr(unit_type, "area_sqm", None)
    if area_sqm is not None:
        area = float(area_sqm)
        specs.append(f"{area:g}㎡")
    bathrooms = getattr(unit_type, "bathrooms", None)
    if bathrooms:
        specs.append(f"{bathrooms}卫")
    if specs:
        facts.append(" · ".join(specs))

    requested_amenities = [
        str(value).strip() for value in (filters.get("amenities") or [])
        if str(value).strip()
    ]
    available_amenities = list(dict.fromkeys([
        *[
            str(value).strip()
            for value in (getattr(unit_type, "amenities", None) or [])
            if str(value).strip()
        ],
        *[
            str(value).strip()
            for value in (getattr(institute, "amenities", None) or [])
            if str(value).strip()
        ],
    ]))
    if requested_amenities:
        available_by_key = {value.casefold(): value for value in available_amenities}
        matched = [
            available_by_key[value.casefold()]
            for value in requested_amenities
            if value.casefold() in available_by_key
        ]
        if matched:
            facts.append(f"所需配套：{'、'.join(matched[:3])}")
    elif available_amenities:
        facts.append(f"配有{'、'.join(available_amenities[:3])}")

    if school_name and commute:
        walk_min = commute.get("walk_min")
        transit_min = commute.get("transit_min")
        commute_text = ""
        if walk_min is not None:
            commute_text = f"到{school_name}步行约{walk_min}分钟"
        elif transit_min is not None:
            commute_text = f"到{school_name}公交约{transit_min}分钟"
        if commute_text:
            if commute.get("source") == "lookup_table":
                commute_text += "（估算）"
            facts.append(commute_text)

    offer = " ".join(str(getattr(unit_type, "special_offer", None) or "").split())
    if offer:
        facts.append(f"优惠：{offer[:36]}{'…' if len(offer) > 36 else ''}")

    available_rooms = int(item.get("available_rooms") or 0)
    if available_rooms > 0:
        facts.append(f"目前{available_rooms}套可租")

    min_stay_months = getattr(unit_type, "min_stay_months", None)
    if min_stay_months:
        facts.append(f"{min_stay_months}个月起租")

    return "；".join(facts[:6]) + "。"


def _fallback_extract_filters(message: str) -> dict[str, Any]:
    """模型不可用时提取高置信度条件，让任务边界仍可可靠工作。"""
    text = message.strip()
    lowered = text.casefold()
    extracted: dict[str, Any] = {}

    def _last_pattern_hit(
        patterns: tuple[tuple[str, re.Pattern[str]], ...],
    ) -> tuple[str, int] | None:
        """返回最后出现的规范值与位置；同位置优先更完整的写法。"""
        latest: tuple[int, int, str] | None = None
        for canonical, pattern in patterns:
            for match in pattern.finditer(lowered):
                candidate = (match.end(), len(match.group(0)), canonical)
                if latest is None or candidate[:2] > latest[:2]:
                    latest = candidate
        return (latest[2], latest[0]) if latest else None

    country_hit = _last_pattern_hit((
        ("SG", re.compile(r"新加坡|\bsingapore\b", re.IGNORECASE)),
        ("GB", re.compile(
            r"英国|英國|英格兰|英格蘭|\bunited kingdom\b|\bgreat britain\b|\buk\b|\bgb\b",
            re.IGNORECASE,
        )),
        ("HK", re.compile(r"(?:中国|中國)?香港|\bhong kong\b|\bhk\b", re.IGNORECASE)),
        ("US", re.compile(
            r"美国|美國|\bunited states(?: of america)?\b|\busa\b",
            re.IGNORECASE,
        )),
        ("CN", re.compile(r"中国大陆|中國大陸|国内|國內|\bmainland china\b|\bchina\b", re.IGNORECASE)),
    ))
    if country_hit:
        extracted["country"] = country_hit[0]

    city_hit = _last_pattern_hit((
        ("London", re.compile(r"伦敦|倫敦|\blondon\b", re.IGNORECASE)),
        ("Singapore", re.compile(r"新加坡|\bsingapore\b", re.IGNORECASE)),
        ("Hong Kong", re.compile(r"香港|\bhong kong\b", re.IGNORECASE)),
        ("Los Angeles", re.compile(r"洛杉矶|洛杉磯|\blos angeles\b|\bLA\b", re.IGNORECASE)),
    ))
    if city_hit:
        extracted["city"] = city_hit[0]

    institution_matches = list(_FALLBACK_INSTITUTION_PATTERN.finditer(text))
    institution_match = institution_matches[-1] if institution_matches else None
    if institution_match:
        extracted["institution"] = institution_match.group(1).upper()

    currency_hit = _last_pattern_hit((
        ("SGD", re.compile(r"新币|新幣|新加坡元|\bsgd\b|s\$", re.IGNORECASE)),
        ("GBP", re.compile(r"英镑|英鎊|镑|鎊|\bgbp\b|£", re.IGNORECASE)),
        ("HKD", re.compile(r"港币|港幣|港元|\bhkd\b|hk\$", re.IGNORECASE)),
        ("USD", re.compile(r"美元|美金|\busd\b|(?<![A-Za-z])\$", re.IGNORECASE)),
        ("CNY", re.compile(r"人民币|人民幣|\bcny\b|(?<!新加坡)(?<!港)[元块]", re.IGNORECASE)),
    ))
    if currency_hit:
        extracted["currency"] = currency_hit[0]

    institution_markets = {
        "NUS": ("SG", "Singapore", "SGD"),
        "NTU": ("SG", "Singapore", "SGD"),
        "SMU": ("SG", "Singapore", "SGD"),
        "SUTD": ("SG", "Singapore", "SGD"),
        "UCL": ("GB", "London", "GBP"),
        "LSE": ("GB", "London", "GBP"),
        "KCL": ("GB", "London", "GBP"),
        "QMUL": ("GB", "London", "GBP"),
        "HKU": ("HK", "Hong Kong", "HKD"),
        "CUHK": ("HK", "Hong Kong", "HKD"),
        "HKUST": ("HK", "Hong Kong", "HKD"),
        "UCLA": ("US", "Los Angeles", "USD"),
        "USC": ("US", "Los Angeles", "USD"),
    }
    if institution_match:
        institution = institution_match.group(1).upper()
        inferred_country, inferred_city, inferred_currency = institution_markets[institution]
        institution_end = institution_match.end()
        # 绕弯表达以最后一次学校修正为准；学校之后另说币种时仍尊重用户原话。
        if country_hit is None or institution_end > country_hit[1]:
            extracted["country"] = inferred_country
        if city_hit is None or institution_end > city_hit[1]:
            extracted["city"] = inferred_city
        if currency_hit is None or institution_end > currency_hit[1]:
            extracted["currency"] = inferred_currency

    price_patterns = (
        # “预算 down to S$1,750”“budget £1,500”以及常见中文改价表达。
        r"(?:预算|月租|租金|价格|\bbudget\b|\bmonthly rent\b|\brent\b)"
        r"[^\d。！？]{0,28}(?:s\$|hk\$|£|\$)?\s*(\d[\d,]*(?:\.\d+)?)",
        r"(?:最多|最高|上限|封顶|不超过|降到|改成|改为|调到|"
        r"\bup to\b|\bunder\b|\bdown to\b|\bmax(?:imum)?\b)"
        r"[^\d。！？]{0,12}(?:s\$|hk\$|£|\$)?\s*(\d[\d,]*(?:\.\d+)?)",
        r"(\d[\d,]*(?:\.\d+)?)\s*"
        r"(?:新币|新幣|新加坡元|sgd|英镑|英鎊|镑|鎊|gbp|港币|港幣|港元|hkd|"
        r"美元|美金|usd|人民币|人民幣|cny|元|块)?\s*"
        r"(?:以内|以下|之内|封顶|最多|不超过|\bor less\b|\bmaximum\b)",
    )
    price_matches = [
        (match.start(), match.group(1))
        for pattern in price_patterns
        for match in re.finditer(pattern, lowered, re.IGNORECASE)
    ]
    if price_matches:
        _, raw_price = max(price_matches, key=lambda item: item[0])
        extracted["price_max"] = float(raw_price.replace(",", ""))

    if re.search(r"\bstudio\b|单间|开间", lowered, re.IGNORECASE):
        extracted["property_type"] = "studio"
    elif re.search(r"\bshared\b|合租", lowered, re.IGNORECASE):
        extracted["property_type"] = "shared"

    amenity_signals = (
        ("独立卫浴", ("独立卫浴", "独卫", "ensuite")),
        ("健身房", ("健身房", "gym")),
        ("泳池", ("泳池", "游泳池", "pool")),
    )
    positive_amenities: list[str] = []
    for label, signals in amenity_signals:
        signal_pattern = "|".join(map(re.escape, signals))
        excluded = re.search(
            rf"(?:不要|排除|避开|不考虑)[^，。；]{{0,8}}(?:{signal_pattern})",
            lowered,
            re.IGNORECASE,
        )
        if any(signal in lowered for signal in signals) and not excluded:
            positive_amenities.append(label)
    if positive_amenities:
        extracted["amenities"] = positive_amenities

    return extracted


# ── 确定性评分（模块级函数，SearchAgent + ToolRegistry 共用） ──

def score_properties(
    candidates: list[UnitType],
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

    prices = [float(p.base_rent) for p in candidates]
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
        price_diff = abs(float(p.base_rent) - target_price)
        price_score = max(0, 100 - (price_diff / max(price_range, 1)) * 100)
        area = float(p.area_sqm) if p.area_sqm else 0
        space_score = min(100, (min(area / max((p.bedrooms or 0) * 20 + 15, 1), 2.0)) * 60 + 20) if area > 0 else 60
        facility_score = 60
        if p.image_urls:
            facility_score += 15
        if getattr(p.institute, "address", None):
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
        if p.image_urls:
            highlights.append("有实拍图片")
        if getattr(p.institute, "district", None):
            highlights.append(f"位于{p.institute.district}")

        scored.append({"property": p, "score": round(total, 1), "highlights": highlights[:3]})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


def _props_text(props: list[UnitType]) -> str:
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

    async def extract_filters(self, message: str) -> dict[str, Any]:
        """只提取本轮明确条件；边界判断和搜索执行复用同一份结果。"""
        extracted = _fallback_extract_filters(message)
        llm = get_llm_service()
        if not llm.is_available:
            return extracted
        try:
            model_result = await llm.complete_json(
                EXTRACT_FILTERS_PROMPT,
                message,
                temperature=0.0,
                max_tokens=400,
            )
        except Exception:
            logger.debug("LLM 提取搜索条件失败")
            return extracted
        if not isinstance(model_result, dict):
            return extracted
        for key, value in model_result.items():
            # null 只代表本轮没提到，不能覆盖确定性提取或承担清除语义。
            if value is None or value == "":
                continue
            extracted[key] = value
        return extracted

    # ── 主入口 ────────────────────────────────────────────────────

    async def search(
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        extracted_filters: dict[str, Any] | None = None,
        clear_fields: Collection[str] | None = None,
        token_sink: Callable[[str], Awaitable[None]] | None = None,
        status_sink: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """检索 + LLM 推荐；SSE 调用方可直接接收模型原始 token。"""
        filters = filters or {}
        llm = get_llm_service()

        # 1. 提取结构化条件。dispatcher 可预先提取供任务边界判断，避免二次调用。
        extracted = (
            dict(extracted_filters)
            if extracted_filters is not None
            else await self.extract_filters(message)
        )

        # 清除意图只接受 dispatcher 已确认的字段；模型返回的 null 或与清除
        # 冲突的猜测都不能重新写回本轮搜索。
        cleared = set(clear_fields or ())
        for key in cleared:
            extracted.pop(key, None)
        for metadata_key in ("hard_filters", "soft_preferences"):
            values = extracted.get(metadata_key)
            if isinstance(values, list):
                extracted[metadata_key] = [value for value in values if value not in cleared]

        def _pick(key: str, default=None):
            """自然语言本轮条件优先于历史/搜索页上下文。"""
            value = extracted.get(key)
            if value is not None and value != "":
                return value
            value = filters.get(key)
            return value if value is not None and value != "" else default

        country = _normalize_country(_pick("country"))
        city = _pick("city")
        district = _pick("district")
        normalized_cleared_fields: set[str] = set()
        if district and str(district).lower().strip() in _EN_TO_CN_CITY:
            district = _EN_TO_CN_CITY[str(district).lower().strip()]
        if _is_singapore_scope(district) and country in (None, "SG"):
            # 模型旧提示或历史会话可能把城市国家“新加坡”写进 district。
            # 这里转换为数据库真实结构，并通知 dispatcher 清除旧区域快照。
            country = "SG"
            city = city or "Singapore"
            district = None
            normalized_cleared_fields.add("district")
            extracted["country"] = country
            extracted["city"] = city
            extracted.pop("district", None)
        elif country and extracted.get("country") not in (None, ""):
            extracted["country"] = country
        price_min = _pick("price_min")
        price_max = _pick("price_max")
        bedrooms = _pick("bedrooms")
        property_type = _pick("property_type")

        # ── 货币换算 ──
        # 推断房源目标币种：从 district/country 推断，默认 GBP
        target_currency = str(_pick("currency") or _infer_currency(district, country)).upper()
        if price_min is not None:
            price_min = resolve_search_price(message, float(price_min), target_currency)
        if price_max is not None:
            price_max = resolve_search_price(message, float(price_max), target_currency)

        # 硬约束字段合并
        amenities: list[str] | None = _pick("amenities")
        room_type: str | None = _pick("room_type")
        bathrooms: int | None = _pick("bathrooms")
        area_min: float | None = _pick("area_min")
        area_max: float | None = _pick("area_max")
        min_lease_months: int | None = _pick("min_lease_months")
        max_lease_months: int | None = _pick("max_lease_months")
        available_from: str | None = _pick("available_from")

        # 2. 学校查找（查 universities 表获取坐标）
        institution_name = _pick("institution")
        distance_km = extracted.get("distance_km", 5.0)  # P0 硬约束：默认学校周边 5km
        if not isinstance(distance_km, (int, float)) or distance_km < 0.5 or distance_km > 50.0:
            distance_km = 5.0

        commute_mode = _pick("commute_mode")
        commute_minutes = _pick("commute_minutes")
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

        # 大学匹配成功后用 Institute.city 做城市约束；不要把城市写入 district，
        # main 的结构化地址中两者是独立字段。
        institution_city = None
        if uni_info:
            uni_city = (uni_info.get("city") or "").strip()
            uni_city_cn = _EN_TO_CN_CITY.get(uni_city.lower(), uni_city)
            institution_city = uni_city or None
            if district and str(district).strip().lower() in {
                uni_city.lower(), uni_city_cn.lower(),
            }:
                district = None

        # 查询文本
        query_parts = [message]
        if country:
            query_parts.append(country)
        if institution_name and not uni_info:
            query_parts.append(institution_name)
        query_text = " ".join(p for p in query_parts if p)

        # P0 硬约束构建
        merged_filters = {
            "country": country or _normalize_country(uni_info.get("country") if uni_info else None),
            "city": city or institution_city,
            "currency": target_currency,
            "institute_id": _pick("institute_id"),
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
            "female_only": _pick("female_only"),
        }

        # 3. 搜索 unit_types（主搜索表）+ JOIN institutes + 聚合 rooms 库存
        unit_results = await self.property_service.search_unit_types(
            district=district,
            country=merged_filters["country"],
            city=merged_filters["city"],
            institute_id=merged_filters["institute_id"],
            price_min=Decimal(str(price_min)) if price_min else None,
            price_max=Decimal(str(price_max)) if price_max else None,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            property_type=property_type or room_type,
            amenities=amenities,
            area_min=area_min,
            area_max=area_max,
            available_from=available_from,
            max_min_stay_months=max_lease_months or min_lease_months,
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
        if status_sink is not None:
            await status_sink("generating", "正在生成推荐回复")
        recommendation_school_name = (
            str(uni_info.get("name") or institution_name or "")
            if uni_info else str(institution_name or "")
        )
        recommendation_commutes: dict[int, dict[str, Any]] = {}
        source_info = f"\n\n【检索】共 {len(unit_results)} 种户型"
        reply_streamed = False
        if llm.is_available and unit_results:
            streamed_parts: list[str] = []
            try:
                top_n = min(3, len(unit_results))
                hard_filters = extracted.get("hard_filters", [])
                soft_prefs = extracted.get("soft_preferences", [])
                p2 = extracted.get("p2_highlights", [])
                school = institution_name or ""
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

                    # 通勤数据：静态查表 → InstituteCommute → None
                    commute_data = None
                    tbl = _lookup_commute(school, district)
                    if tbl:
                        commute_data = {"walk_min": tbl[0], "transit_min": tbl[1], "source": "lookup_table"}
                    elif uni_info:
                        try:
                            from app.models.institute_commute import InstituteCommute
                            sub_stmt = (
                                select(InstituteCommute)
                                .where(
                                    InstituteCommute.institute_id == inst.id,
                                    InstituteCommute.university_id == uni_info["id"],
                                )
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
                        "currency": str(getattr(t, "currency", "") or ""),
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
                    recommendation_commutes[t.id] = commute_data

                user_prompt = json.dumps(ctx, ensure_ascii=False, indent=2)
                # SSE 路径直接转发供应商返回的原始增量 token；普通接口仍保持
                # 一次性 complete_text，避免改变现有非流式契约。
                try:
                    messages = [
                        {"role": "system", "content": RECOMMEND_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ]
                    if token_sink is None:
                        reply = await llm.complete_text(
                            messages=messages,
                            temperature=0.25,
                            max_tokens=700,
                        )
                        reply = (reply or "").strip()
                    else:
                        async for token in llm.complete_text_stream(
                            messages=messages,
                            temperature=0.25,
                            max_tokens=700,
                        ):
                            if not token:
                                continue
                            streamed_parts.append(token)
                            await token_sink(token)
                        reply = "".join(streamed_parts)
                except Exception:
                    raise  # 交给外层 except 做规则降级
                if not reply or (token_sink is None and len(reply) < 20):
                    raise ValueError("LLM 返回空回复")
                reply = reply + source_info
                if token_sink is not None:
                    await token_sink(source_info)
                    reply_streamed = True
            except Exception as _e:
                logger.exception("LLM 推荐生成失败，降级为规则摘要: %s", _e)
                # 规则降级也沿用紧凑标记，避免恢复成冗长的五项列表。
                lines = [f"【结论】找到 {len(unit_results)} 种户型，先看前 {min(3, len(unit_results))} 个。"]
                for i, item in enumerate(unit_results[:3], 1):
                    t = item["unit_type"]
                    inst = item["institute"]
                    commute_data = recommendation_commutes.get(t.id)
                    if commute_data is None and school:
                        estimated = _lookup_commute(school, inst.district or "")
                        if estimated:
                            commute_data = {
                                "walk_min": estimated[0],
                                "transit_min": estimated[1],
                                "source": "lookup_table",
                            }
                    reason = _build_recommendation_reason(
                        item,
                        merged_filters,
                        school_name=recommendation_school_name,
                        commute=commute_data,
                    )
                    sym = get_symbol(getattr(t, "currency", None))
                    lines.append(
                        f"【推荐{i}】{inst.name} · {t.name}："
                        f"{sym}{float(t.base_rent):.0f}/月。{reason}"
                    )
                lines.append("【怎么选】可以先把更符合你优先级的户型加入候选清单。")
                fallback_reply = "\n".join(lines) + source_info
                if token_sink is not None and streamed_parts:
                    suffix = "\n\n（AI 生成中断，以上内容可能不完整。）" + source_info
                    await token_sink(suffix)
                    reply = "".join(streamed_parts) + suffix
                    reply_streamed = True
                else:
                    reply = fallback_reply
        elif not llm.is_available:
            reply = f"为您找到 {len(unit_results)} 种户型。{AI_UNAVAILABLE_HINT}{source_info}"
        else:
            reply = f"为您找到 {len(unit_results)} 种户型。尝试放宽条件或换个区域试试？{source_info}"

        def _recommendation(item: dict, rank: int) -> dict[str, Any]:
            unit_type = item["unit_type"]
            institute = item["institute"]
            commute_data = recommendation_commutes.get(unit_type.id)
            if commute_data is None and institution_name:
                estimated = _lookup_commute(
                    str(institution_name),
                    str(institute.district or ""),
                )
                if estimated:
                    commute_data = {
                        "walk_min": estimated[0],
                        "transit_min": estimated[1],
                        "source": "lookup_table",
                    }
            return {
                # 对外保留 property_id 字段名，但值严格为 UnitType.id。
                "property_id": unit_type.id,
                "rank": rank,
                "match_reason": _build_recommendation_reason(
                    item,
                    merged_filters,
                    school_name=recommendation_school_name,
                    commute=commute_data,
                ),
                "pros": [],
                "cons": [],
                "property": unit_type,
                "source_metadata": {
                    "entity": "unit_type",
                    "unit_type_id": unit_type.id,
                    "institute_id": institute.id,
                },
            }

        all_recs = [
            _recommendation(item, rank)
            for rank, item in enumerate(unit_results, 1)
        ]
        top_picks = all_recs[:3]
        visible_recs = all_recs[:MAX_RECOMMENDATION_CARDS]

        return {
            "reply": reply, "recommendations": visible_recs,
            "recommendation_total": len(all_recs), "ai_available": llm.is_available,
            "extracted_filters": extracted, "top_picks": top_picks,
            "score_gap": None, "relaxation_level": 0,
            "candidate_snapshot": [ut["unit_type"].id for ut in unit_results],
            "normalized_cleared_filters": sorted(normalized_cleared_fields),
            "source_info": source_info,
            "effective_filters": {
                key: value for key, value in merged_filters.items()
                if value is not None and key not in {"near_lat", "near_lng", "near_distance_km"}
            },
            "_reply_streamed": reply_streamed,
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
            "status": UnitTypeStatus.available.value,
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

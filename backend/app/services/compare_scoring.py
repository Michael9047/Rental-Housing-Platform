"""房源对比 —— 确定性加权评分

评分与"讲道理"分离：分数由本模块用真实数据计算（可复现、可审计），
LLM 只负责解释分数背后的优劣势，不允许修改分数。

四个维度（各归一化到 0-100，在参与对比的房源集合内相对计算）：
- price   价格：越便宜越高
- commute 通勤：POI 交通类目里最近站点越近越高（无数据取中性分）
- space   空间：面积越大越高（无面积取中性分）
- rating  评分：机构真实评价均分（1-5 星 → 0-100；无评价取中性分）

用户优先级决定四维权重，"哪套更好"跟着用户看重的维度走。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── 优先级权重 ────────────────────────────────────────────────────

PRIORITY_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {"price": 0.30, "commute": 0.25, "space": 0.25, "rating": 0.20},
    "budget":   {"price": 0.50, "commute": 0.20, "space": 0.15, "rating": 0.15},
    "commute":  {"price": 0.20, "commute": 0.50, "space": 0.15, "rating": 0.15},
    "space":    {"price": 0.20, "commute": 0.15, "space": 0.50, "rating": 0.15},
}

PRIORITY_LABELS: dict[str, str] = {
    "balanced": "均衡",
    "budget": "预算优先",
    "commute": "通勤优先",
    "space": "空间优先",
}

DIMENSION_LABELS: dict[str, str] = {
    "price": "价格",
    "commute": "通勤",
    "space": "空间",
    "rating": "评价",
}

NEUTRAL_SCORE = 60  # 缺数据时的中性分：不奖励也不重罚


# ── 周边偏好注册表（chip 生成 / 搜索排序 / 对比展示 三处共用）────────
#
# 用户在渐进选房里能点的"离XX近"偏好，统一在此定义：
#   key          稳定标识，进 filters.poi_requirements[].type 与前端 filterPatch
#   category     对应 PropertyPOI.poi_data 的中文类目键
#   label        chip 上展示的中文文案
#   near_m       "近"的软阈值（米）——用于排序打分与展示"最近"判定
#   compare_icon 对比卡片/表格里该维度的图标
#
# 想新增一类周边（如"离公园近"），只在此加一行即可，三处逻辑自动生效。

@dataclass(frozen=True)
class POIPreference:
    key: str
    category: str
    label: str
    near_m: int
    compare_icon: str
    short: str        # 对比里展示的短名（如"地铁""超市"），拼距离用


POI_PREFERENCES: dict[str, POIPreference] = {
    "transit": POIPreference("transit", "交通", "离地铁/公交近", 500, "🚇", "地铁"),
    "supermarket": POIPreference("supermarket", "购物", "近超市", 500, "🛒", "超市"),
    "hospital": POIPreference("hospital", "医疗", "近医院/药店", 1000, "🏥", "医院"),
    "gym": POIPreference("gym", "生活", "周边有健身房", 800, "🏋️", "健身房"),
    "dining": POIPreference("dining", "美食", "吃饭方便", 500, "🍜", "餐厅"),
}


def get_poi_preference(key: str) -> POIPreference | None:
    """按 key 取周边偏好定义（未知 key 返回 None）。"""
    return POI_PREFERENCES.get(key)


# type 别名 → pref key：前端注入 key，LLM 可能提取中文类目/具体关键词
_POI_ALIASES: dict[str, str] = {}
for _pref in POI_PREFERENCES.values():
    _POI_ALIASES[_pref.key] = _pref.key
    _POI_ALIASES[_pref.category] = _pref.key
_POI_ALIASES.update({
    "地铁": "transit", "地铁站": "transit", "公交": "transit", "公交站": "transit",
    "车站": "transit", "subway": "transit", "metro": "transit", "station": "transit",
    "超市": "supermarket", "便利店": "supermarket", "商场": "supermarket", "grocery": "supermarket",
    "医院": "hospital", "药店": "hospital", "药房": "hospital", "诊所": "hospital",
    "pharmacy": "hospital", "clinic": "hospital",
    "健身房": "gym", "健身": "gym", "fitness": "gym",
    "餐厅": "dining", "餐馆": "dining", "吃饭": "dining", "食阁": "dining", "restaurant": "dining",
})


def normalize_poi_type(raw: str | None) -> str | None:
    """把任意 POI 类型写法（key/中文类目/关键词）规范化为 POI_PREFERENCES 的 key。"""
    if not raw:
        return None
    return _POI_ALIASES.get(str(raw).strip().lower()) or _POI_ALIASES.get(str(raw).strip())


def normalize_poi_requirements(reqs: list[dict] | None) -> list[str]:
    """把 filters.poi_requirements（[{"type":...}]）规范化为去重的 pref key 列表，保持顺序。"""
    if not reqs:
        return []
    keys: list[str] = []
    for r in reqs:
        if not isinstance(r, dict):
            continue
        key = normalize_poi_type(r.get("type"))
        if key and key not in keys:
            keys.append(key)
    return keys


def poi_preference_by_category(category: str) -> POIPreference | None:
    """按中文类目反查偏好定义（对比展示用）。"""
    for pref in POI_PREFERENCES.values():
        if pref.category == category:
            return pref
    return None



def normalize_priority(priority: str | None) -> str:
    return priority if priority in PRIORITY_WEIGHTS else "balanced"


# ── 指标 ─────────────────────────────────────────────────────────

@dataclass
class PropertyMetrics:
    property_id: int
    price: float
    area: float | None = None          # ㎡，可能未知
    transit_meters: int | None = None  # 最近交通站点距离（米），来自 POI
    rating: float | None = None        # 机构评价均分 1-5
    review_count: int = 0


_DISTANCE_RE = re.compile(r"([\d.]+)\s*(km|m|公里|千米|米)", re.IGNORECASE)


def parse_distance_meters(text: str | None) -> int | None:
    """把 POI 距离字符串（'500m' / '1km' / '1.2公里'）解析成米"""
    if not text:
        return None
    m = _DISTANCE_RE.search(str(text))
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit in ("km", "公里", "千米"):
        value *= 1000
    return int(value)


def nearest_poi_meters(poi_data: dict | None, category: str) -> int | None:
    """从 POI categories JSON 里取指定类目中最近设施的距离（米）。

    poi_data 形如 {"交通": [{"name","distance":"350m","keyword":"地铁站"}], "购物": [...], ...}。
    category 为中文类目键（交通/医疗/购物/美食/生活），无数据返回 None。
    """
    if not poi_data:
        return None
    entries = poi_data.get(category) or []
    distances = [
        d for d in (parse_distance_meters(e.get("distance")) for e in entries if isinstance(e, dict))
        if d is not None
    ]
    return min(distances) if distances else None


def nearest_transit_meters(poi_data: dict | None) -> int | None:
    """从 POI categories JSON 里取交通类目中最近的站点距离（米）。

    保留独立函数：对比评分的通勤维度专用，语义清晰。
    """
    return nearest_poi_meters(poi_data, "交通")


# ── 各维度打分（0-100）──────────────────────────────────────────

def _relative_score(value: float, lo: float, hi: float, *, lower_is_better: bool) -> int:
    """集合内线性归一化到 [40, 100]：最优 100、最差 40，避免 0 分观感过差"""
    if hi <= lo:
        return 80  # 全部相同
    ratio = (value - lo) / (hi - lo)
    if lower_is_better:
        ratio = 1 - ratio
    return round(40 + 60 * ratio)


def _commute_score(meters: int | None) -> int:
    """通勤按绝对距离分档（跨集合可比）：步行 5 分钟内满分"""
    if meters is None:
        return NEUTRAL_SCORE
    if meters <= 400:
        return 100
    if meters <= 800:
        return 90
    if meters <= 1200:
        return 75
    if meters <= 2000:
        return 60
    return 45


def _rating_score(rating: float | None) -> int:
    if rating is None:
        return NEUTRAL_SCORE
    return round(max(1.0, min(5.0, rating)) * 20)


def compute_scores(
    metrics: list[PropertyMetrics], priority: str | None = None
) -> dict[int, dict]:
    """计算每套房源的四维分与加权总分。

    返回 {property_id: {"total": int, "breakdown": {"price": int, "commute": int, "space": int, "rating": int}}}
    """
    if not metrics:
        return {}

    weights = PRIORITY_WEIGHTS[normalize_priority(priority)]

    prices = [m.price for m in metrics]
    lo_p, hi_p = min(prices), max(prices)
    areas = [m.area for m in metrics if m.area is not None]
    lo_a, hi_a = (min(areas), max(areas)) if areas else (0.0, 0.0)

    result: dict[int, dict] = {}
    for m in metrics:
        breakdown = {
            "price": _relative_score(m.price, lo_p, hi_p, lower_is_better=True),
            "commute": _commute_score(m.transit_meters),
            "space": (
                _relative_score(m.area, lo_a, hi_a, lower_is_better=False)
                if m.area is not None and areas
                else NEUTRAL_SCORE
            ),
            "rating": _rating_score(m.rating),
        }
        total = round(sum(breakdown[k] * w for k, w in weights.items()))
        result[m.property_id] = {"total": total, "breakdown": breakdown}
    return result


def poi_distance_score(meters: int | None, near_m: int) -> int:
    """给"到某类周边设施的距离"打分（0-100，越近越高），用于搜索软排序。

    near_m 是该类目的"近"阈值：≤near_m 视为很近给高分，之后按档递减；
    无数据取中性分（不奖励也不重罚，保证无 POI 的房源不被硬性沉底）。
    """
    if meters is None:
        return NEUTRAL_SCORE
    if meters <= near_m:
        return 100
    if meters <= near_m * 2:
        return 85
    if meters <= near_m * 4:
        return 65
    return 45


def format_poi_distance(meters: int | None) -> str | None:
    """周边设施距离展示文本，如 '350m' / '1.2km'。"""
    if meters is None:
        return None
    if meters >= 1000:
        return f"{meters / 1000:.1f}km"
    return f"{meters}m"


def format_commute(meters: int | None) -> str | None:
    """通勤展示文本，如 '距地铁/公交约500m'"""
    if meters is None:
        return None
    if meters >= 1000:
        return f"最近交通站点约{meters / 1000:.1f}km"
    return f"最近交通站点约{meters}m"

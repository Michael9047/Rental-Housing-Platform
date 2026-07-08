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


def nearest_transit_meters(poi_data: dict | None) -> int | None:
    """从 POI categories JSON 里取交通类目中最近的站点距离（米）"""
    if not poi_data:
        return None
    entries = poi_data.get("交通") or []
    distances = [
        d for d in (parse_distance_meters(e.get("distance")) for e in entries if isinstance(e, dict))
        if d is not None
    ]
    return min(distances) if distances else None


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


def format_commute(meters: int | None) -> str | None:
    """通勤展示文本，如 '距地铁/公交约500m'"""
    if meters is None:
        return None
    if meters >= 1000:
        return f"最近交通站点约{meters / 1000:.1f}km"
    return f"最近交通站点约{meters}m"

"""渐进选房 —— POI 软排序 + 引导选项生成

配合 SearchAgent：
- rank_by_poi：按用户选过的周边偏好（离地铁/超市/医院/健身房近），
  对候选户型做软重排（不排除无数据房源）。
- build_guided_options：根据当前 filters + 候选里真实存在的 POI 类目 + 尚未选过的
  维度，产出结果下方可点击的引导 chip（携带 filter_patch，点击即收窄）。

HEAD: POI 挂在 Institute 上（InstitutePOI.institute_id），经 UnitType.institute_id
桥接。同 institute 下所有户型共享同一份 POI 数据。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ── POI 偏好定义（原属 compare_scoring，PR50 清理后移至本模块本地）──

from dataclasses import dataclass

@dataclass(frozen=True)
class PoiPreference:
    key: str
    label: str
    category: str
    near_m: int = 500
    icon: str = ""

POI_PREFERENCES: dict[str, PoiPreference] = {
    "metro":  PoiPreference("metro",  "近地铁", "交通", 500, "🚇"),
    "bus":    PoiPreference("bus",    "近公交", "交通", 300, "🚌"),
    "market": PoiPreference("market", "近超市", "购物", 500, "🛒"),
    "food":   PoiPreference("food",   "近美食", "美食", 500, "🍜"),
    "hospital": PoiPreference("hospital", "近医院", "医疗", 1000, "🏥"),
    "gym":    PoiPreference("gym",    "近健身房", "生活", 500, "💪"),
}

def get_poi_preference(key: str) -> PoiPreference | None:
    return POI_PREFERENCES.get(key)

def nearest_poi_meters(poi_data: dict | None, category: str) -> int | None:
    """返回指定类目下最近 POI 的距离（米）。处理 \"55m\"/\"1.2km\" 等格式。"""
    if not poi_data or not isinstance(poi_data, dict):
        return None
    entries = poi_data.get(category)
    if not entries or not isinstance(entries, list):
        return None
    distances = []
    for e in entries:
        dist = e.get("distance") or e.get("distance_m")
        if dist is not None:
            try:
                s = str(dist).strip().lower().replace(" ", "")
                if s.endswith("km"):
                    distances.append(int(float(s[:-2]) * 1000))
                elif s.endswith("m"):
                    distances.append(int(float(s[:-1])))
                else:
                    distances.append(int(float(s)))
            except (ValueError, TypeError):
                pass
    return min(distances) if distances else None

def poi_distance_score(meters: int | None, near_threshold: int = 500) -> float:
    """距离转 0-1 分：near_threshold 米内满分，超过则递减。"""
    if meters is None:
        return 0.5
    return max(0.0, min(1.0, near_threshold / max(meters, 1)))

def normalize_poi_requirements(raw: list[str] | None) -> list[str]:
    """标准化传入的周边偏好 key 列表（去重、仅保留已注册类目）。"""
    if not raw:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for v in raw:
        key = str(v).strip().casefold()
        if key and key in POI_PREFERENCES and key not in seen:
            seen.add(key)
            result.append(key)
    return result

logger = logging.getLogger(__name__)

# chip 展示上限：一次最多给用户几个引导选项，避免选项过载
MAX_GUIDED_OPTIONS = 5


async def load_unit_type_poi(
    session: AsyncSession, unit_type_ids: list[int]
) -> dict[int, dict]:
    """批量加载一组 unit_type 的 POI 数据（poi_data JSON）。

    HEAD: InstitutePOI.institute_id → Institute → UnitType.institute_id。
    返回 {unit_type_id: poi_data_dict}；无 POI 的户型不在返回里。
    """
    if not unit_type_ids:
        return {}

    from app.models.poi import InstitutePOI
    from app.models.unit_type import UnitType
    from app.models.institute import Institute

    try:
        stmt = (
            select(UnitType.id, InstitutePOI.poi_data)
            .join(Institute, UnitType.institute_id == Institute.id)
            .join(InstitutePOI, InstitutePOI.institute_id == Institute.id)
            .where(UnitType.id.in_(unit_type_ids))
        )
        rows = (await session.execute(stmt)).all()
    except Exception:
        logger.exception("加载 unit_type POI 失败，POI 排序降级为不排序")
        return {}

    result: dict[int, dict] = {}
    for ut_id, poi_data in rows:
        if ut_id is None or not poi_data:
            continue
        if ut_id not in result:
            result[ut_id] = poi_data
    return result


def attach_poi_distances(
    unit_results: list[dict],
    poi_by_ut: dict[int, dict],
) -> None:
    """给每个候选注入 `_poi_distances`：所有注册类目里有数据的最近距离。

    与是否选中偏好无关——首轮（用户还没选任何周边）卡片上也要能展示
    「地铁 350m / 超市 200m」。原地修改，不返回值。
    """
    for ut in unit_results:
        poi_data = poi_by_ut.get(ut["unit_type"].id)
        distances: dict[str, int] = {}
        for pref in POI_PREFERENCES.values():
            meters = nearest_poi_meters(poi_data, pref.category)
            if meters is not None:
                distances[pref.key] = meters
        ut["_poi_distances"] = distances


def rank_by_poi(
    unit_results: list[dict],
    poi_by_ut: dict[int, dict],
    pref_keys: list[str],
) -> list[dict]:
    """按用户选过的周边偏好对候选做软重排（稳定排序，不排除任何房源）。

    每套的 POI 分 = 各选中类目 poi_distance_score 的均值；无数据取中性分。
    原顺序（价格升序）作为同分时的稳定次序保留。
    返回：重排后的 unit_results（每项注入 `_poi_score`）。
    注意：`_poi_distances` 由 attach_poi_distances 统一注入（全类目），此处不覆盖。
    """
    if not pref_keys or not unit_results:
        return unit_results

    prefs = [get_poi_preference(k) for k in pref_keys]
    prefs = [p for p in prefs if p is not None]
    if not prefs:
        return unit_results

    for idx, ut in enumerate(unit_results):
        ut_id = ut["unit_type"].id
        poi_data = poi_by_ut.get(ut_id)
        scores: list[int] = []
        for pref in prefs:
            meters = nearest_poi_meters(poi_data, pref.category)
            scores.append(poi_distance_score(meters, pref.near_m))
        ut["_poi_score"] = sum(scores) / len(scores) if scores else 0.0
        ut["_orig_index"] = idx

    # 高分在前；同分保持原价格升序（_orig_index 升序）
    return sorted(
        unit_results,
        key=lambda u: (-u.get("_poi_score", 0.0), u.get("_orig_index", 0)),
    )


def _detect_available_categories(poi_by_ut: dict[int, dict]) -> set[str]:
    """统计候选池里真实出现过的 POI 类目（中文），用于只推有数据的引导选项。"""
    cats: set[str] = set()
    for poi_data in poi_by_ut.values():
        if isinstance(poi_data, dict):
            for cat, entries in poi_data.items():
                if entries:
                    cats.add(cat)
    return cats


def build_guided_options(
    active_filters: dict[str, Any],
    poi_by_ut: dict[int, dict],
    result_count: int,
) -> list[dict]:
    """生成结果下方的引导选项（预设维度 + 结构化 filter_patch）。

    规则：
    - 只推「候选池里真有数据」且「用户还没选过」的 POI 维度；
    - 结果数够多时补充预算/独卫等收窄维度；
    - 每个 chip 带 filter_patch，前端点击后并入累积 filters 重发。
    """
    # 结果太少就不再引导收窄（避免筛到 0）
    if result_count <= 3:
        return []

    chosen_keys = set(normalize_poi_requirements(active_filters.get("poi_requirements")))
    available_cats = _detect_available_categories(poi_by_ut)

    options: list[dict] = []

    # 1. POI 维度：按 POI_PREFERENCES 顺序，推还没选过且候选里有数据的
    for key, pref in POI_PREFERENCES.items():
        if key in chosen_keys:
            continue
        if pref.category not in available_cats:
            continue
        options.append({
            "label": pref.label,
            "message": f"最好{pref.label}",
            "filter_patch": {"poi_requirements": [{"type": key}]},
            "kind": "poi",
            "icon": pref.icon,
        })

    # 2. 预算收窄：仅当已有预算上限时，给一个"再便宜点"
    price_max = active_filters.get("price_max")
    if price_max:
        try:
            lowered = int(float(price_max) * 0.85)
            options.append({
                "label": f"再便宜点（{lowered}以内）",
                "message": f"预算降到{lowered}以内",
                "filter_patch": {"price_max": lowered},
                "kind": "budget",
                "icon": "💰",
            })
        except (TypeError, ValueError):
            pass

    # 3. 独卫：未指定卫浴时补一个常见硬需求
    if not active_filters.get("bathrooms"):
        options.append({
            "label": "要独立卫浴",
            "message": "最好有独立卫浴",
            "filter_patch": {"amenities": ["独立卫浴"]},
            "kind": "amenity",
            "icon": "🚿",
        })

    return options[:MAX_GUIDED_OPTIONS]


TOO_FEW_RESULTS_MAX = 3
TOO_MANY_RESULTS_MIN = 8
ROOM_FILTER_FIELDS = ("property_type", "room_type", "bedrooms")
RELAXATION_ORDER = ("amenities", "poi", "budget", "room_type")


def _option(
    *,
    label: str,
    message: str,
    kind: str,
    icon: str,
    filter_patch: dict[str, Any] | None = None,
    clear_fields: list[str] | None = None,
) -> dict[str, Any]:
    """构造前后端一致的引导选项协议。"""
    return {
        "label": label,
        "message": message,
        "filter_patch": filter_patch,
        "clear_fields": clear_fields or [],
        "kind": kind,
        "icon": icon,
    }


def _trace_for_field(
    relaxation_trace: list[dict[str, Any]],
    field_name: str,
) -> dict[str, Any] | None:
    for trace in relaxation_trace:
        if trace.get("field") != field_name:
            continue
        if int(trace.get("after_count") or 0) <= int(trace.get("before_count") or 0):
            continue
        return trace
    return None


def build_result_guidance(
    active_filters: dict[str, Any],
    result_count: int,
    relaxation_trace: list[dict[str, Any]] | None,
    attempted_relaxations: list[str] | None,
) -> list[dict[str, Any]]:
    """按真实结果数生成收窄或逐层放宽指引；合适区间不打扰用户。"""
    traces = relaxation_trace or []
    attempted = set(attempted_relaxations or [])

    if result_count >= TOO_MANY_RESULTS_MIN:
        options: list[dict[str, Any]] = []
        if not any(active_filters.get(field) is not None for field in ROOM_FILTER_FIELDS):
            options.append(_option(
                label="选择户型",
                message="我想先确定户型",
                kind="narrow_room_type",
                icon="🏠",
            ))
        if active_filters.get("price_max") is None:
            options.append(_option(
                label="设定预算上限",
                message="我想补充预算上限",
                kind="narrow_budget",
                icon="💰",
            ))
        if active_filters.get("commute_minutes") is None:
            has_destination = bool(
                active_filters.get("institution") or active_filters.get("institute_id")
            )
            options.append(_option(
                label="设置通勤时间" if has_destination else "补充学校或目的地",
                message="通勤时间控制在 30 分钟内" if has_destination else "我想补充通勤目的地",
                filter_patch={"commute_minutes": 30} if has_destination else None,
                kind="narrow_commute" if has_destination else "narrow_destination",
                icon="🚌" if has_destination else "🎓",
            ))
        return options[:3]

    if result_count > TOO_FEW_RESULTS_MAX:
        return []

    for layer in RELAXATION_ORDER:
        if layer in attempted:
            continue
        if layer == "amenities" and active_filters.get("amenities"):
            trace = _trace_for_field(traces, "amenities")
            count = f"（约 {trace['after_count']} 个）" if trace else ""
            return [_option(
                label=f"放宽房内设施{count}",
                message="暂不限制房内设施要求",
                clear_fields=["amenities"],
                kind="relax_amenities",
                icon="↗",
            )]
        if layer == "poi" and active_filters.get("poi_requirements"):
            trace = _trace_for_field(traces, "poi_requirements")
            count = f"（约 {trace['after_count']} 个）" if trace else ""
            return [_option(
                label=f"放宽周边配套{count}",
                message="暂不限制周边配套要求",
                clear_fields=["poi_requirements"],
                kind="relax_poi",
                icon="↗",
            )]
        if layer == "budget" and active_filters.get("price_max") is not None:
            trace = _trace_for_field(traces, "price_max")
            current = float(active_filters["price_max"])
            suggested = int(current * 1.2 + 0.9999)
            after_count = None
            if trace:
                suggested = int((trace.get("suggested_filters") or {}).get("price_max") or suggested)
                after_count = int(trace.get("after_count") or 0)
            count = f"（约 {after_count} 个）" if after_count else ""
            return [_option(
                label=f"预算放宽到 {suggested}{count}",
                message=f"把预算上限放宽到 {suggested}",
                filter_patch={"price_max": suggested},
                kind="relax_budget",
                icon="↗",
            )]
        if layer == "room_type" and any(active_filters.get(field) is not None for field in ROOM_FILTER_FIELDS):
            return [_option(
                label="放宽户型要求",
                message="暂不限制户型要求",
                clear_fields=list(ROOM_FILTER_FIELDS),
                kind="relax_room_type",
                icon="↗",
            )]
    return []

# 兼容别名（search_agent 中引用）
_load_poi_batch = load_unit_type_poi
# reload trigger

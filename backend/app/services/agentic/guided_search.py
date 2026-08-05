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

from app.services.compare_scoring import (
    POI_PREFERENCES,
    get_poi_preference,
    nearest_poi_meters,
    normalize_poi_requirements,
    poi_distance_score,
)

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
            "icon": pref.compare_icon,
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

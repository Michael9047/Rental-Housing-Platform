"""房源事实服务 —— 批量读取缓存 POI，并补充一次批量通勤计算。"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi import PropertyPOI
from app.models.property import Property
from app.services.commute_service import CommuteDestination, calculate_commute_batch_resilient
from app.services.preference_state import canonical_poi_type

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class POISummary:
    """适合排序和展示的缓存 POI 摘要；缺失值始终保留为 None。"""

    nearest_transit_m: int | None = None
    nearest_supermarket_m: int | None = None
    supermarket_count_1km: int | None = None
    nearest_gym_m: int | None = None
    gym_count_1km: int | None = None
    nearest_medical_m: int | None = None
    medical_count_2km: int | None = None

    def distance_for(self, poi_type: str) -> int | None:
        canonical = canonical_poi_type(poi_type)
        return {
            "transit": self.nearest_transit_m,
            "supermarket": self.nearest_supermarket_m,
            "gym": self.nearest_gym_m,
            "medical": self.nearest_medical_m,
        }.get(canonical)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommuteSummary:
    """一次批量路线计算中的单套房源结果。"""

    dist_km: float
    walk_min: int
    bike_min: int
    drive_min: int
    transit_min: int
    source: str
    transit_verified: bool

    def minutes_for(self, mode: str | None) -> int | None:
        return {
            "walking": self.walk_min,
            "bicycling": self.bike_min,
            "driving": self.drive_min,
            "transit": self.transit_min,
        }.get(mode or "")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataCompleteness:
    """区分“确实很远”和“没有缓存/坐标，无法判断”。"""

    poi_cache_available: bool
    poi_categories_available: list[str] = field(default_factory=list)
    poi_coverage: float = 0.0
    coordinates_available: bool = False
    commute_available: bool = False
    commute_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PropertyFactBundle:
    """一套房源的 POI、通勤和数据完整性。"""

    property_id: int
    poi: POISummary
    commute: CommuteSummary | None
    data_completeness: DataCompleteness

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "poi": self.poi.to_dict(),
            "commute": self.commute.to_dict() if self.commute else None,
            "data_completeness": self.data_completeness.to_dict(),
        }


_SUMMARY_CATEGORIES: dict[str, tuple[str, ...]] = {
    "transit": ("bus_station", "subway_station", "transit"),
    "supermarket": ("supermarket",),
    "gym": ("gym",),
    "medical": ("medical", "pharmacy"),
}


def _distance_to_meters(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0, int(round(value)))
    text = str(value).strip().lower().replace("米", "m")
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(km|m)?", text)
    if not match:
        return None
    number = float(match.group(1))
    if number < 0:
        return None
    return int(round(number * 1000 if match.group(2) == "km" else number))


def summarize_map_poi_data(map_poi_data: dict[str, Any] | None) -> tuple[POISummary, list[str]]:
    """把 PropertyPOI.map_poi_data 转成固定维度摘要，不触发外部请求。"""
    if not isinstance(map_poi_data, dict):
        return POISummary(), []
    categories = map_poi_data.get("categories")
    if not isinstance(categories, dict):
        return POISummary(), []

    distances: dict[str, list[int]] = {}
    available: list[str] = []
    for summary_key, source_keys in _SUMMARY_CATEGORIES.items():
        values: list[int] = []
        seen_items: set[str] = set()
        category_present = False
        for source_key in source_keys:
            items = categories.get(source_key)
            if not isinstance(items, list):
                continue
            category_present = True
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_key = str(
                    item.get("id")
                    or f"{item.get('name', '')}:{item.get('lat', '')}:{item.get('lng', '')}"
                )
                if item_key in seen_items:
                    continue
                distance = _distance_to_meters(item.get("distance"))
                if distance is not None:
                    values.append(distance)
                    seen_items.add(item_key)
        if category_present:
            available.append(summary_key)
        distances[summary_key] = values

    def nearest(key: str) -> int | None:
        return min(distances[key]) if distances[key] else None

    def count_within(key: str, limit_m: int) -> int | None:
        if key not in available:
            return None
        return sum(distance <= limit_m for distance in distances[key])

    return POISummary(
        nearest_transit_m=nearest("transit"),
        nearest_supermarket_m=nearest("supermarket"),
        supermarket_count_1km=count_within("supermarket", 1000),
        nearest_gym_m=nearest("gym"),
        gym_count_1km=count_within("gym", 1000),
        nearest_medical_m=nearest("medical"),
        medical_count_2km=count_within("medical", 2000),
    ), available


class PropertyFactService:
    """为候选房源批量组装事实；同步排序链路只读 POI 缓存。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_poi_cache(
        self,
        property_ids: list[int],
    ) -> dict[int, tuple[POISummary, list[str], bool]]:
        if not property_ids:
            return {}
        try:
            rows = await self.session.scalars(
                select(PropertyPOI).where(PropertyPOI.property_id.in_(property_ids))
            )
        except Exception:
            logger.warning("批量读取 POI 缓存失败，按数据缺失继续推荐", exc_info=True)
            return {}
        result: dict[int, tuple[POISummary, list[str], bool]] = {}
        for poi in rows:
            summary, available = summarize_map_poi_data(poi.map_poi_data)
            result[poi.property_id] = (summary, available, bool(poi.map_poi_data))
        return result

    @staticmethod
    async def _load_commutes(
        properties: list[Property],
        origin_lat: float | None,
        origin_lng: float | None,
        country: str | None,
        city: str | None,
    ) -> dict[int, CommuteSummary]:
        if origin_lat is None or origin_lng is None:
            return {}
        destinations = [
            CommuteDestination(dest_id=prop.id, lat=float(prop.latitude), lng=float(prop.longitude))
            for prop in properties
            if prop.latitude is not None and prop.longitude is not None
        ]
        if not destinations:
            return {}
        try:
            batch = await calculate_commute_batch_resilient(
                origin_lat=origin_lat,
                origin_lng=origin_lng,
                destinations=destinations,
                country=country,
                city=city,
            )
        except Exception:
            logger.warning("批量通勤计算失败，按数据缺失继续推荐", exc_info=True)
            return {}
        summaries: dict[int, CommuteSummary] = {}
        for item in batch.results:
            property_id = int(item.dest_id)
            source = item.source
            summaries[property_id] = CommuteSummary(
                dist_km=item.dist_km,
                walk_min=item.walk_min,
                bike_min=item.bike_min,
                drive_min=item.drive_min,
                transit_min=item.transit_min,
                source=source,
                # ORS 不提供公共交通；高德公交调用失败时也可能退回估算。
                transit_verified=bool(getattr(item, "transit_verified", False)),
            )
        return summaries

    async def build_bundles(
        self,
        properties: Iterable[Property],
        *,
        origin_lat: float | None = None,
        origin_lng: float | None = None,
        country: str | None = None,
        city: str | None = None,
    ) -> dict[int, PropertyFactBundle]:
        """POI 单次 SQL 查询与通勤批量请求并行执行。"""
        props = list(properties)
        property_ids = [prop.id for prop in props]
        poi_cache, commutes = await asyncio.gather(
            self._load_poi_cache(property_ids),
            self._load_commutes(props, origin_lat, origin_lng, country, city),
        )

        bundles: dict[int, PropertyFactBundle] = {}
        expected_category_count = len(_SUMMARY_CATEGORIES)
        for prop in props:
            poi_summary, available, cache_available = poi_cache.get(
                prop.id, (POISummary(), [], False)
            )
            commute = commutes.get(prop.id)
            completeness = DataCompleteness(
                poi_cache_available=cache_available,
                poi_categories_available=available,
                poi_coverage=round(len(available) / expected_category_count, 2),
                coordinates_available=prop.latitude is not None and prop.longitude is not None,
                commute_available=commute is not None,
                commute_source=commute.source if commute else None,
            )
            bundles[prop.id] = PropertyFactBundle(
                property_id=prop.id,
                poi=poi_summary,
                commute=commute,
                data_completeness=completeness,
            )
        return bundles


def satisfies_poi_requirements(
    bundle: PropertyFactBundle,
    requirements: list[dict[str, Any]] | None,
) -> bool:
    """硬 POI 条件只接受有缓存证据且距离达标的房源。"""
    for requirement in requirements or []:
        if not isinstance(requirement, dict):
            continue
        distance = bundle.poi.distance_for(str(requirement.get("type") or ""))
        limit = requirement.get("target_m", requirement.get("max_distance_m"))
        try:
            limit_m = int(float(limit)) if limit is not None else None
        except (TypeError, ValueError):
            limit_m = None
        if distance is None or limit_m is None or distance > limit_m:
            return False
    return True

"""对比 Agent 综合数据采集 —— 一次性拉取房源全部关联数据

复用 agent_service._gather_compare_metrics 中的 POI + Review 查询模式，
并扩展到 amenities / deposit / floor 等 Property 已有但未用在对比中的字段。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi import PropertyPOI
from app.models.property import Property
from app.services.compare_scoring import (
    PropertyMetrics,
    format_commute,
    nearest_transit_meters,
)
from app.services.safety_scoring import SafetyScoringService

logger = logging.getLogger(__name__)


@dataclass
class EnrichedPropertyData:
    """一条房源的全部可对比信息"""
    property_id: int
    title: str = ""
    district: str = ""
    address: str = ""
    price_monthly: float = 0.0
    area_sqm: float | None = None
    bedrooms: int = 0
    bathrooms: int = 0
    property_type: str = ""
    description: str | None = None
    amenities: list[str] = field(default_factory=list)
    deposit_amount: int | None = None
    deposit_type: str | None = None
    service_fee_rate: float | None = None
    min_lease_months: int = 12
    floor: int | None = None
    room_number: str | None = None
    image_count: int = 0
    transit_meters: int | None = None
    transit_display: str | None = None
    rating: float | None = None
    review_count: int = 0
    safety_score: float | None = None

    @property
    def metrics(self) -> PropertyMetrics:
        return PropertyMetrics(
            property_id=self.property_id,
            price=self.price_monthly,
            area=self.area_sqm,
            transit_meters=self.transit_meters,
            rating=self.rating,
            review_count=self.review_count,
            safety_score=self.safety_score,
        )


async def gather_comprehensive_metrics(
    props: list[Property],
    session: AsyncSession,
    safety_service: SafetyScoringService | None = None,
) -> dict[int, EnrichedPropertyData]:
    """一次性拉取一批房源的所有可对比数据。"""
    if not props:
        return {}

    ids = [p.id for p in props]

    # ── POI 数据 ──
    poi_rows = (
        await session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id.in_(ids))
        )
    ).scalars().all()
    poi_map: dict[int, PropertyPOI] = {poi.property_id: poi for poi in poi_rows}

    # ── Review 数据（raw SQL—DB schema 仍是 institute_id/rating）──
    inst_ids = sorted({p.institute_id for p in props if p.institute_id is not None})
    inst_review: dict[int, dict[str, Any]] = {}
    if inst_ids:
        raw = text(
            "SELECT institute_id, AVG(rating)::float AS avg_rating, COUNT(id) AS cnt "
            "FROM reviews WHERE institute_id = ANY(:ids) AND status = 'approved' "
            "GROUP BY institute_id"
        )
        rows = (await session.execute(raw, {"ids": inst_ids})).all()
        for iid, avg, cnt in rows:
            inst_review[iid] = {"rating": avg, "count": cnt}
    # 映射 property -> institute
    review_map: dict[int, dict[str, Any]] = {}
    for p in props:
        ri = inst_review.get(p.institute_id)
        if ri:
            review_map[p.id] = ri

    # ── 安全评分 ──
    # 优先从 PropertyPOI.safety_data 缓存读取
    safety_map: dict[int, float] = {}
    uncached_ids: list[int] = []
    uncached_coords: dict[int, tuple[float, float]] = {}
    for p in props:
        poi = poi_map.get(p.id)
        if poi and poi.safety_data and poi.safety_data.get("safety_score"):
            safety_map[p.id] = poi.safety_data["safety_score"]
        elif p.latitude is not None and p.longitude is not None:
            uncached_ids.append(p.id)
            uncached_coords[p.id] = (float(p.latitude), float(p.longitude))

    if uncached_ids and safety_service:
        try:
            lats = {pid: lat for pid, (lat, _) in uncached_coords.items()}
            lngs = {pid: lng for pid, (_, lng) in uncached_coords.items()}
            addrs = {p.id: (p.address or p.title or "") for p in props if p.id in uncached_ids}
            country = props[0].country if props else None
            results = await safety_service.score_properties(
                uncached_ids, country=country,
                latitudes=lats, longitudes=lngs, addresses=addrs,
            )
            for pid, r in results.items():
                safety_map[pid] = r.score
        except Exception:
            logger.warning("安全评分获取失败，使用中性分", exc_info=True)

    # ── 组装 ──
    result: dict[int, EnrichedPropertyData] = {}
    for p in props:
        poi = poi_map.get(p.id)
        poi_data = poi.poi_data if poi else None
        transit_m = nearest_transit_meters(poi_data)
        rev = review_map.get(p.id)

        result[p.id] = EnrichedPropertyData(
            property_id=p.id,
            title=p.title,
            district=p.district or "",
            address=p.address or "",
            price_monthly=float(p.price_monthly),
            area_sqm=float(p.area_sqm) if p.area_sqm else None,
            bedrooms=p.bedrooms,
            bathrooms=p.bathrooms,
            property_type=p.property_type.value if p.property_type else "",
            description=p.description[:300] if p.description else None,
            amenities=p.amenities or [],
            deposit_amount=p.deposit_amount,
            deposit_type=p.deposit_type.value if p.deposit_type else None,
            service_fee_rate=p.service_fee_rate,
            min_lease_months=p.min_lease_months,
            floor=p.floor,
            room_number=p.room_number,
            image_count=len(p.images) if p.images else 0,
            transit_meters=transit_m,
            transit_display=format_commute(transit_m),
            rating=rev["rating"] if rev else None,
            review_count=rev["count"] if rev else 0,
            safety_score=safety_map.get(p.id),
        )

    return result

"""户型对比综合数据采集 —— 聚合 UnitType、Institute、POI、评价与安全数据。"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi import InstitutePOI
from app.models.review import Review, ReviewStatus
from app.models.unit_type import UnitType
from app.services.compare_scoring import PropertyMetrics, format_commute, nearest_transit_meters
from app.services.safety_scoring import SafetyScoringService


@dataclass
class EnrichedPropertyData:
    """一个 UnitType 及所属公寓的全部可对比信息。"""

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
    min_lease_months: int = 3
    floor: int | None = None
    room_number: str | None = None
    image_count: int = 0
    transit_meters: int | None = None
    transit_display: str | None = None
    rating: float | None = None
    review_count: int = 0
    safety_score: float | None = None
    institute_id: int | None = None
    currency: str | None = None

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
            currency=self.currency,
        )


async def gather_comprehensive_metrics(
    props: list[UnitType],
    session: AsyncSession,
    safety_service: SafetyScoringService | None = None,
) -> dict[int, EnrichedPropertyData]:
    """一次性拉取 2-5 个户型的公寓级补充数据。"""
    if not props:
        return {}

    institute_ids = {prop.institute_id for prop in props}
    poi_rows = list(await session.scalars(
        select(InstitutePOI).where(InstitutePOI.institute_id.in_(institute_ids))
    ))
    poi_by_institute = {poi.institute_id: poi for poi in poi_rows}

    review_rows = await session.execute(
        select(Review.institute_id, func.avg(Review.rating), func.count(Review.id))
        .where(
            Review.institute_id.in_(institute_ids),
            Review.status == ReviewStatus.approved,
        )
        .group_by(Review.institute_id)
    )
    reviews = {
        institute_id: (float(average), int(count))
        for institute_id, average, count in review_rows
    }

    safety_by_unit: dict[int, float] = {}
    missing_by_country: dict[str, list[UnitType]] = {}
    for prop in props:
        poi = poi_by_institute.get(prop.institute_id)
        cached = poi.safety_data if poi and isinstance(poi.safety_data, dict) else {}
        score = cached.get("safety_score")
        if isinstance(score, (int, float)):
            safety_by_unit[prop.id] = float(score)
        elif safety_service is not None:
            country = str(getattr(prop.institute, "country", "") or "")
            missing_by_country.setdefault(country, []).append(prop)

    if safety_service is not None:
        for country, units in missing_by_country.items():
            ids = [unit.id for unit in units]
            latitudes = {
                unit.id: float(unit.institute.latitude)
                for unit in units if unit.institute.latitude is not None
            }
            longitudes = {
                unit.id: float(unit.institute.longitude)
                for unit in units if unit.institute.longitude is not None
            }
            try:
                scored = await safety_service.score_properties(
                    ids,
                    country=country,
                    latitudes=latitudes,
                    longitudes=longitudes,
                )
                safety_by_unit.update({unit_id: result.score for unit_id, result in scored.items()})
            except Exception:
                # 外部安全源失败时保留 None，评分层会按中性分处理。
                pass

    output: dict[int, EnrichedPropertyData] = {}
    for prop in props:
        institute = prop.institute
        poi = poi_by_institute.get(prop.institute_id)
        transit = nearest_transit_meters(poi.poi_data if poi else None)
        rating, review_count = reviews.get(prop.institute_id, (None, 0))
        property_type = prop.property_type
        deposit_type = prop.deposit_type
        amenities = list(dict.fromkeys([
            *[str(value) for value in (prop.amenities or []) if value],
            *[str(value) for value in (institute.amenities or []) if value],
        ]))
        output[prop.id] = EnrichedPropertyData(
            property_id=prop.id,
            title=" · ".join(
                value for value in (institute.name_cn or institute.name, prop.name) if value
            ),
            district=institute.district or "",
            address=institute.address or "",
            price_monthly=float(prop.base_rent),
            area_sqm=float(prop.area_sqm) if prop.area_sqm is not None else None,
            bedrooms=prop.bedrooms,
            bathrooms=prop.bathrooms,
            property_type=(property_type.value if hasattr(property_type, "value") else str(property_type or "")),
            description=prop.description[:300] if prop.description else None,
            amenities=amenities,
            deposit_amount=prop.deposit_amount,
            deposit_type=(deposit_type.value if hasattr(deposit_type, "value") else str(deposit_type or "")) or None,
            service_fee_rate=None,
            min_lease_months=prop.min_stay_months,
            floor=None,
            room_number=None,
            image_count=len(prop.image_urls or []),
            transit_meters=transit,
            transit_display=format_commute(transit),
            rating=rating,
            review_count=review_count,
            safety_score=safety_by_unit.get(prop.id),
            institute_id=prop.institute_id,
            currency=prop.currency,
        )
    return output

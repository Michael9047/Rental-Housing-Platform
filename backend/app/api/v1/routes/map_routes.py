from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.core.config import get_settings
from app.models.unit_type import UnitType, UnitTypeStatus
from app.models.institute import Institute

router = APIRouter()


@router.get("/properties")
async def get_map_properties(
    session: AsyncSession = Depends(get_db_session),
    sw_lat: float | None = Query(None, description="South-west latitude"),
    sw_lng: float | None = Query(None, description="South-west longitude"),
    ne_lat: float | None = Query(None, description="North-east latitude"),
    ne_lng: float | None = Query(None, description="North-east longitude"),
    country: str | None = Query(None, min_length=2, max_length=2, description="国家/地区代码"),
    limit: int = Query(default=500, le=1000),
):
    """根据视口框选返回轻量房源列表，用于地图展示"""
    stmt = (
        select(UnitType)
        .join(Institute, UnitType.institute_id == Institute.id)
        .options(selectinload(UnitType.institute).selectinload(Institute.images))
        .where(
            UnitType.status == UnitTypeStatus.available,
            Institute.latitude.isnot(None),
            Institute.longitude.isnot(None),
        )
    )

    if country:
        stmt = stmt.where(Institute.country == country.upper())

    if sw_lat is not None and sw_lng is not None and ne_lat is not None and ne_lng is not None:
        stmt = stmt.where(
            Institute.latitude.between(sw_lat, ne_lat),
            Institute.longitude.between(sw_lng, ne_lng),
        )

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    unit_types = result.unique().scalars().all()

    items = []
    for ut in unit_types:
        inst = ut.institute
        primary_url = None
        if inst and inst.images:
            primary = next((img for img in inst.images if img.is_primary), None)
            chosen = primary or inst.images[0]
            primary_url = f"/api/v1/uploads/{chosen.filename}"

        items.append({
            "id": ut.id,
            "title": ut.name,
            "district": inst.district if inst else None,
            "country": inst.country if inst else None,
            "address": inst.address if inst else None,
            "price_monthly": ut.base_rent,
            "bedrooms": ut.bedrooms,
            "bathrooms": ut.bathrooms,
            "property_type": ut.property_type.value if ut.property_type else None,
            "latitude": float(inst.latitude) if inst and inst.latitude else None,
            "longitude": float(inst.longitude) if inst and inst.longitude else None,
            "area_sqm": ut.area_sqm,
            "primary_image_url": primary_url,
        })

    return {"count": len(items), "items": items}


@router.get("/config")
async def get_map_config(country: str | None = Query(None, min_length=2, max_length=2)):
    """返回地图配置，根据国家/地区返回对应地图引擎的 Key 和默认中心点"""
    settings = get_settings()
    country_upper = country.upper() if country else "CN"

    # 中国大陆默认中心（北京）
    # 海外默认中心（新加坡）
    if country_upper == "CN":
        center = [39.9042, 116.4074]
        zoom = 11
        map_provider = "amap"
        map_key = settings.amap_js_key or settings.amap_web_key or ""
    else:
        center = [1.3521, 103.8198]  # 新加坡
        zoom = 12
        map_provider = "google"
        map_key = settings.gm_api_key or ""

    return {
        "map_provider": map_provider,
        "map_key": map_key,
        "center": center,
        "zoom": zoom,
    }

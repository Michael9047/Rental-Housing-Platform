from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import get_settings
from app.models.property import Property

router = APIRouter()


@router.get("/properties")
async def get_map_properties(
    session: AsyncSession = Depends(get_db_session),
    sw_lat: float | None = Query(None, description="South-west latitude"),
    sw_lng: float | None = Query(None, description="South-west longitude"),
    ne_lat: float | None = Query(None, description="North-east latitude"),
    ne_lng: float | None = Query(None, description="North-east longitude"),
    limit: int = Query(default=500, le=1000),
):
    """Return lightweight property list for map display. Optional viewport filter."""
    stmt = select(Property).where(
        Property.status == "available",
        Property.latitude.isnot(None),
        Property.longitude.isnot(None),
    )

    if sw_lat is not None and sw_lng is not None and ne_lat is not None and ne_lng is not None:
        stmt = stmt.where(
            Property.latitude.between(sw_lat, ne_lat),
            Property.longitude.between(sw_lng, ne_lng),
        )

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    properties = result.scalars().all()

    return {
        "count": len(properties),
        "items": [
            {
                "id": p.id,
                "title": p.title,
                "district": p.district,
                "address": p.address,
                "price_monthly": p.price_monthly,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "property_type": p.property_type,
                "latitude": float(p.latitude) if p.latitude else None,
                "longitude": float(p.longitude) if p.longitude else None,
                "area_sqm": p.area_sqm,
            }
            for p in properties
        ],
    }


@router.get("/config")
async def get_map_config():
    """Return map configuration including API keys."""
    settings = get_settings()
    return {
        "amap_js_key": settings.amap_js_key or settings.amap_api_key or settings.amap_web_key or "",
        "center": [39.9042, 116.4074],  # 北京
        "zoom": 11,
    }

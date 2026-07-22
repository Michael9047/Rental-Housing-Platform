from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.services.map_service import MapService

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
    items = await MapService(session).list_properties_in_bounds(
        sw_lat=sw_lat,
        sw_lng=sw_lng,
        ne_lat=ne_lat,
        ne_lng=ne_lng,
        country=country,
        limit=limit,
    )
    return {"count": len(items), "items": items}


@router.get("/config")
async def get_map_config(country: str | None = Query(None, min_length=2, max_length=2)):
    """返回地图配置，根据国家/地区返回对应地图引擎的 Key 和默认中心点"""
    return MapService.get_map_config(country)

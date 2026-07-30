from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.property import Property
from app.schemas.poi import POIResponse, MapPOIResponse
from app.services.google_poi_service import GooglePOIService

router = APIRouter()


@router.post("/{property_id}/generate", response_model=POIResponse, status_code=status.HTTP_201_CREATED)
async def generate_poi(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse:
    """手动触发 POI 生成（强制 Google Maps 重新搜索）。"""
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    poi_service = GooglePOIService()
    poi = await poi_service.generate_and_save(prop, session)
    if not poi:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="POI generation failed")
    return poi


@router.get("/{property_id}", response_model=POIResponse | None)
async def get_poi(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse | None:
    """获取房源 POI 数据，不存在时自动生成。"""
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    poi_service = GooglePOIService()
    poi = await poi_service.get_or_generate_poi(property_id, session)

    if poi:
        return poi

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="周边数据暂不可用，请稍后重试",
    )


@router.get("/{property_id}/map", response_model=MapPOIResponse)
async def get_map_pois(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MapPOIResponse:
    """获取房源地图 POI 预生成数据（PropertyMapCard 小地图用）。"""
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    poi_service = GooglePOIService()
    data = await poi_service.get_or_generate_map_pois(property_id, session)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="地图周边数据暂不可用，请稍后重试",
        )

    return MapPOIResponse(
        property_id=property_id,
        generated_at=None,
        search_radius_m=data.get("search_radius_m", 2000),
        categories=data.get("categories", {}),
    )

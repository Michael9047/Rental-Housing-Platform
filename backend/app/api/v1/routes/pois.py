from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.property import Property
from app.schemas.poi import POIResponse, MapPOIResponse
from app.services.poi_service import POIService

router = APIRouter()


@router.post("/{property_id}/generate", response_model=POIResponse, status_code=status.HTTP_201_CREATED)
async def generate_poi(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse:
    """手动触发 POI 生成（强制刷新）。"""
    # 先确认房源存在
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    poi_service = POIService(session)
    poi = await poi_service.generate_poi_for_property(prop, force=True)
    if not poi:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="POI generation failed")
    return poi


@router.get("/{property_id}", response_model=POIResponse | None)
async def get_poi(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse | None:
    """获取房源 POI 数据，不存在时自动生成。

    房源存在但 POI 生成失败时返回 503，前端展示错误。
    仅房源本身不存在时返回 404。
    """
    # 先确认房源存在
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    poi_service = POIService(session)
    poi = await poi_service.get_or_generate_poi(property_id)

    if poi:
        return poi

    # 房源存在但 POI 生成失败
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="周边数据暂不可用，请稍后重试",
    )


@router.get("/{property_id}/map", response_model=MapPOIResponse)
async def get_map_pois(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MapPOIResponse:
    """获取房源地图 POI 预生成数据（PropertyMapCard 小地图用）。

    优先返回缓存，不存在时实时生成并持久化。
    仅房源不存在时返回 404。
    """
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    poi_service = POIService(session)
    data = await poi_service.get_or_generate_map_pois(property_id)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="地图周边数据暂不可用，请稍后重试",
        )

    poi = await poi_service.get_poi(property_id)
    return MapPOIResponse(
        property_id=property_id,
        generated_at=poi.generated_at if poi else None,
        search_radius_m=data.get("search_radius_m", 3000),
        categories=data.get("categories", {}),
    )

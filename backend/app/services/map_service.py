"""地图服务 —— 统一封装视口房源查询、轻量序列化与地图引擎配置。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.property import Property


class MapService:
    """不依赖 Agent 的确定性地图业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_properties_in_bounds(
        self,
        *,
        sw_lat: float | None = None,
        sw_lng: float | None = None,
        ne_lat: float | None = None,
        ne_lng: float | None = None,
        country: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """返回地图视口内的可用房源轻量数据。"""
        stmt = (
            select(Property)
            .options(selectinload(Property.images))
            .where(
                Property.status == "available",
                Property.latitude.isnot(None),
                Property.longitude.isnot(None),
            )
        )
        if country:
            stmt = stmt.where(Property.country == country.upper())
        if None not in (sw_lat, sw_lng, ne_lat, ne_lng):
            stmt = stmt.where(
                Property.latitude.between(sw_lat, ne_lat),
                Property.longitude.between(sw_lng, ne_lng),
            )

        result = await self.session.execute(stmt.limit(limit))
        return [self.serialize_property(prop) for prop in result.scalars().all()]

    @staticmethod
    def serialize_property(property_obj: Property) -> dict[str, Any]:
        """序列化地图标记所需字段，不加载房源详情冗余数据。"""
        primary_url = None
        if property_obj.images:
            primary = next((image for image in property_obj.images if image.is_primary), None)
            chosen = primary or property_obj.images[0]
            primary_url = f"/api/v1/uploads/{chosen.filename}"

        return {
            "id": property_obj.id,
            "title": property_obj.title,
            "district": property_obj.district,
            "country": property_obj.country,
            "address": property_obj.address,
            "price_monthly": property_obj.price_monthly,
            "bedrooms": property_obj.bedrooms,
            "bathrooms": property_obj.bathrooms,
            "property_type": property_obj.property_type,
            "latitude": (
                float(property_obj.latitude) if property_obj.latitude is not None else None
            ),
            "longitude": (
                float(property_obj.longitude) if property_obj.longitude is not None else None
            ),
            "area_sqm": property_obj.area_sqm,
            "primary_image_url": primary_url,
        }

    @staticmethod
    def get_map_config(country: str | None = None) -> dict[str, Any]:
        """根据国家/地区返回现有前端兼容的地图引擎配置。"""
        settings = get_settings()
        country_upper = country.upper() if country else "CN"
        if country_upper == "CN":
            return {
                "map_provider": "amap",
                "map_key": settings.amap_js_key or settings.amap_web_key or "",
                "center": [39.9042, 116.4074],
                "zoom": 11,
            }
        return {
            "map_provider": "google",
            "map_key": settings.gm_api_key or "",
            "center": [1.3521, 103.8198],
            "zoom": 12,
        }

from app.models.property import Property, PropertyStatus, PropertyType
from app.services.geocoding_service import AmapGeocodingService, NearbyPoiItem
from app.services.poi_service import POIService

import pytest


class TestPOIGeneration:
    @pytest.mark.asyncio
    async def test_generate_poi_uses_nearby_search(self, session_maker):
        async with session_maker() as session:
            property_obj = Property(
                landlord_id=1,
                title="测试房源",
                address="江苏省苏州市工业园区星湖街1号",
                district="工业园区",
                price_monthly=5000,
                area_sqm=65,
                bedrooms=2,
                bathrooms=1,
                property_type=PropertyType.apartment,
                status=PropertyStatus.available,
                latitude=31.299456,
                longitude=120.585123,
            )
            session.add(property_obj)
            await session.commit()
            await session.refresh(property_obj)

            async def fake_search_nearby(self, location, keyword, *, radius=None, page_size=None, category="周边设施"):
                mapping = {
                    "地铁站": [NearbyPoiItem(name="时代广场站", distance="500m", category=category, keyword=keyword)],
                    "医院": [NearbyPoiItem(name="园区医院", distance="800m", category=category, keyword=keyword)],
                    "学校": [NearbyPoiItem(name="星海学校", distance="1200m", category=category, keyword=keyword)],
                    "超市": [NearbyPoiItem(name="邻里中心超市", distance="600m", category=category, keyword=keyword)],
                }
                return mapping.get(keyword, [])

            original_client = POIService(session).client
            poi_service = POIService(session)
            poi_service.client = None

            from unittest.mock import patch

            with patch.object(AmapGeocodingService, "search_nearby", new=fake_search_nearby):
                poi = await poi_service.generate_poi_for_property(property_obj, force=True)

            assert poi is not None
            assert "周边" in poi.content
            assert poi.poi_data is not None
            assert "交通" in poi.poi_data
            assert any(item["name"] == "时代广场站" for item in poi.poi_data["交通"])

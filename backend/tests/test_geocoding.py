from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.services.geocoding_service import AmapGeocodingService


class TestAmapGeocodingService:
    def _make_response(self, json_data: dict):
        resp = AsyncMock()
        resp.json = lambda: json_data
        resp.raise_for_status = lambda: None
        return resp

    @pytest.mark.asyncio
    async def test_geocode_success(self):
        mock_resp = self._make_response(
            {
                "status": "1",
                "info": "OK",
                "geocodes": [
                    {
                        "formatted_address": "江苏省苏州市工业园区星湖街1号",
                        "location": "120.585123,31.299456",
                        "level": "门牌号",
                        "province": "江苏省",
                        "city": "苏州市",
                        "district": "工业园区",
                    }
                ],
            }
        )

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            service = AmapGeocodingService()
            object.__setattr__(service.settings, "amap_web_key", "test_key")

            result = await service.geocode("江苏省苏州市工业园区星湖街1号", "苏州")

        assert result.longitude == 120.585123
        assert result.latitude == 31.299456
        assert result.formatted_address == "江苏省苏州市工业园区星湖街1号"


class TestGeocodingAPI:
    def _make_response(self, json_data: dict):
        resp = AsyncMock()
        resp.json = lambda: json_data
        resp.raise_for_status = lambda: None
        return resp

    @pytest.mark.asyncio
    async def test_geocode_address_success(self, client: AsyncClient):
        settings = get_settings()
        object.__setattr__(settings, "amap_web_key", "test_key")

        mock_resp = self._make_response(
            {
                "status": "1",
                "info": "OK",
                "geocodes": [
                    {
                        "formatted_address": "江苏省苏州市工业园区星湖街1号",
                        "location": "120.585123,31.299456",
                        "level": "门牌号",
                        "province": "江苏省",
                        "city": "苏州市",
                        "district": "工业园区",
                    }
                ],
            }
        )

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            response = await client.post(
                "/api/v1/geo/geocode",
                json={"address": "江苏省苏州市工业园区星湖街1号", "city": "苏州"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["longitude"] == 120.585123
        assert data["latitude"] == 31.299456
        assert data["formatted_address"] == "江苏省苏州市工业园区星湖街1号"

    @pytest.mark.asyncio
    async def test_geocode_address_requires_key(self, client: AsyncClient):
        settings = get_settings()
        object.__setattr__(settings, "amap_web_key", "")

        response = await client.post(
            "/api/v1/geo/geocode",
            json={"address": "江苏省苏州市工业园区星湖街1号"},
        )

        assert response.status_code == 503
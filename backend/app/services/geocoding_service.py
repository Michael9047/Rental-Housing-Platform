# geocoding_service.py — 多引擎地理编码服务
# 中国大陆 → 高德地图（主），OSM Nominatim（备用）
# 港澳台 + 海外 → Google Maps（主），OSM Nominatim（备用）

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 中国大陆及其它使用高德作为主引擎的国家/地区
_AMAP_PRIMARY_COUNTRIES: frozenset[str] = frozenset({"CN"})

# 海外使用 Google Maps 作为主引擎的国家/地区
_GM_PRIMARY_COUNTRIES: frozenset[str] = frozenset({
    "HK", "MO", "TW", "SG", "GB", "US", "AU", "DE", "FR",
    "NL", "CA", "JP", "KR", "OT",
})


# ---------------------------------------------------------------------------
# 共享数据类
# ---------------------------------------------------------------------------


@dataclass
class GeocodeResult:
    address: str
    latitude: Decimal
    longitude: Decimal
    formatted_address: str | None = None
    level: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None


@dataclass
class NearbyPoiItem:
    name: str
    distance: str | None
    category: str
    keyword: str
    address: str | None = None
    distance_meters: int | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "distance": self.distance or "未知",
            "address": self.address or "",
        }


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------


class BaseGeocodingService(ABC):
    """地理编码服务抽象基类"""

    @abstractmethod
    async def geocode(self, address: str, city: str | None = None) -> GeocodeResult:
        ...

    @abstractmethod
    async def search_nearby(
        self,
        location: str,
        keyword: str,
        *,
        radius: int | None = None,
        page_size: int | None = None,
        category: str = "周边设施",
    ) -> list[NearbyPoiItem]:
        ...


# ---------------------------------------------------------------------------
# 高德地图引擎（中国大陆主引擎）
# ---------------------------------------------------------------------------


class AmapGeocodingService(BaseGeocodingService):
    """高德地图地理编码 + 周边搜索"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def web_key(self) -> str:
        return self.settings.amap_web_key

    async def geocode(self, address: str, city: str | None = None) -> GeocodeResult:
        if not self.web_key:
            raise RuntimeError("AMAP_WEB_KEY is not configured")

        params: dict[str, str] = {
            "key": self.web_key,
            "address": address.strip(),
        }
        if city:
            params["city"] = city.strip()

        timeout = httpx.Timeout(self.settings.amap_geocode_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(self.settings.amap_geocode_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            raise ValueError(f"Geocoding failed: {data.get('info', 'unknown error')}")

        geocodes = data.get("geocodes") or []
        if not geocodes:
            raise ValueError("Geocoding failed: no result returned")

        primary = geocodes[0]
        location = primary.get("location")
        if not location or "," not in location:
            raise ValueError("Geocoding failed: invalid location returned")

        longitude_str, latitude_str = location.split(",", 1)
        return GeocodeResult(
            address=address.strip(),
            latitude=Decimal(latitude_str),
            longitude=Decimal(longitude_str),
            formatted_address=primary.get("formatted_address"),
            level=primary.get("level"),
            province=primary.get("province"),
            city=primary.get("city"),
            district=primary.get("district"),
        )

    async def search_nearby(
        self,
        location: str,
        keyword: str,
        *,
        radius: int | None = None,
        page_size: int | None = None,
        category: str = "周边设施",
    ) -> list[NearbyPoiItem]:
        if not self.web_key:
            raise RuntimeError("AMAP_WEB_KEY is not configured")

        params: dict[str, str] = {
            "key": self.web_key,
            "location": location,
            "keywords": keyword,
            "radius": str(radius or self.settings.amap_nearby_radius_meters),
            "offset": str(page_size or self.settings.amap_nearby_page_size),
            "sortrule": "distance",
        }

        timeout = httpx.Timeout(self.settings.amap_geocode_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(self.settings.amap_around_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            raise ValueError(f"Nearby search failed: {data.get('info', 'unknown error')}")

        return self._parse_pois(data.get("pois") or [], keyword, category)

    @staticmethod
    def _parse_pois(
        pois: list[dict],
        keyword: str,
        category: str,
    ) -> list[NearbyPoiItem]:
        results: list[NearbyPoiItem] = []
        for item in pois:
            name = str(item.get("name") or item.get("pname") or keyword).strip()
            if not name:
                continue
            distance_raw = item.get("distance")
            distance_meters: int | None = None
            distance_text: str | None = None
            if distance_raw is not None and str(distance_raw).strip():
                try:
                    distance_meters = int(float(str(distance_raw).strip()))
                    distance_text = f"{distance_meters}m"
                except ValueError:
                    distance_text = str(distance_raw).strip()

            results.append(
                NearbyPoiItem(
                    name=name,
                    distance=distance_text,
                    distance_meters=distance_meters,
                    category=category,
                    keyword=keyword,
                    address=item.get("address"),
                )
            )

        results.sort(key=lambda poi: poi.distance_meters if poi.distance_meters is not None else 10**9)
        return results


# ---------------------------------------------------------------------------
# Google Maps 引擎（海外主引擎）
# ---------------------------------------------------------------------------


class GoogleGeocodingService(BaseGeocodingService):
    """Google Maps 地理编码 + Places Nearby Search"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def api_key(self) -> str:
        return self.settings.gm_api_key

    async def geocode(self, address: str, city: str | None = None) -> GeocodeResult:
        if not self.api_key:
            raise RuntimeError("GM_API_KEY is not configured")

        full_address = address.strip()
        if city:
            full_address = f"{city}, {full_address}"

        params: dict[str, str] = {
            "key": self.api_key,
            "address": full_address,
        }

        timeout = httpx.Timeout(self.settings.gm_geocode_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(self.settings.gm_geocode_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "OK":
            raise ValueError(f"Google Geocoding failed: {data.get('status', 'unknown error')}")

        results = data.get("results") or []
        if not results:
            raise ValueError("Google Geocoding failed: no result returned")

        primary = results[0]
        geometry = primary.get("geometry", {})
        loc = geometry.get("location", {})
        lat = loc.get("lat")
        lng = loc.get("lng")
        if lat is None or lng is None:
            raise ValueError("Google Geocoding failed: invalid location returned")

        # 解析 address_components 提取行政区域
        province: str | None = None
        city_name: str | None = None
        district: str | None = None
        for comp in primary.get("address_components", []):
            types = comp.get("types", [])
            if "administrative_area_level_1" in types:
                province = comp.get("long_name") or comp.get("short_name")
            if "locality" in types:
                city_name = comp.get("long_name") or comp.get("short_name")
            if "sublocality" in types or "sublocality_level_1" in types:
                district = comp.get("long_name") or comp.get("short_name")

        return GeocodeResult(
            address=address.strip(),
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lng)),
            formatted_address=primary.get("formatted_address"),
            province=province,
            city=city_name or city,
            district=district,
        )

    async def search_nearby(
        self,
        location: str,
        keyword: str,
        *,
        radius: int | None = None,
        page_size: int | None = None,
        category: str = "周边设施",
    ) -> list[NearbyPoiItem]:
        if not self.api_key:
            raise RuntimeError("GM_API_KEY is not configured")

        params: dict[str, str] = {
            "key": self.api_key,
            "location": location,
            "radius": str(radius or self.settings.gm_nearby_radius_meters),
            "keyword": keyword,
        }

        timeout = httpx.Timeout(self.settings.gm_geocode_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(self.settings.gm_nearby_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status", "")
        if status not in ("OK", "ZERO_RESULTS"):
            raise ValueError(f"Google Nearby Search failed: {status}")

        return self._parse_pois(data.get("results") or [], keyword, category)

    @staticmethod
    def _parse_pois(
        results: list[dict],
        keyword: str,
        category: str,
    ) -> list[NearbyPoiItem]:
        items: list[NearbyPoiItem] = []
        for place in results:
            name = place.get("name", "").strip()
            if not name:
                continue

            distance_meters: int | None = None
            distance_text: str | None = None
            # geometry 可能缺失（如 ZERO_RESULTS）
            geometry = place.get("geometry") or {}
            raw_dist = geometry.get("distance") if geometry else None
            if raw_dist is not None:
                try:
                    distance_meters = int(float(raw_dist))
                    if distance_meters >= 1000:
                        distance_text = f"{distance_meters / 1000:.2f}km"
                    else:
                        distance_text = f"{distance_meters}m"
                except (ValueError, TypeError):
                    pass

            items.append(
                NearbyPoiItem(
                    name=name,
                    distance=distance_text,
                    distance_meters=distance_meters,
                    category=category,
                    keyword=keyword,
                    address=place.get("vicinity"),
                )
            )

        items.sort(key=lambda poi: poi.distance_meters if poi.distance_meters is not None else 10**9)
        return items


# ---------------------------------------------------------------------------
# OSM Nominatim 引擎（全球备用引擎）
# ---------------------------------------------------------------------------


class NominatimGeocodingService(BaseGeocodingService):
    """OSM Nominatim 地理编码（无 POI 周边搜索能力，仅 geocode）"""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def geocode(self, address: str, city: str | None = None) -> GeocodeResult:
        full_address = address.strip()
        if city:
            full_address = f"{city}, {full_address}"

        params: dict[str, str] = {
            "q": full_address,
            "format": "json",
            "limit": "1",
            "addressdetails": "1",
        }

        headers = {
            "User-Agent": "RentalHousingPlatform/1.0 (nominatim fallback)",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        timeout = httpx.Timeout(self.settings.nominatim_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            resp = await client.get(self.settings.nominatim_url + "/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        if not data:
            raise ValueError("Nominatim Geocoding failed: no result returned")

        primary = data[0]
        lat = primary.get("lat")
        lon = primary.get("lon")
        if lat is None or lon is None:
            raise ValueError("Nominatim Geocoding failed: invalid location returned")

        addr = primary.get("address") or {}
        return GeocodeResult(
            address=address.strip(),
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lon)),
            formatted_address=primary.get("display_name"),
            province=addr.get("state") or addr.get("province"),
            city=addr.get("city") or addr.get("town") or addr.get("county") or city,
            district=addr.get("suburb") or addr.get("city_district") or addr.get("district"),
        )

    async def search_nearby(
        self,
        location: str,
        keyword: str,
        *,
        radius: int | None = None,
        page_size: int | None = None,
        category: str = "周边设施",
    ) -> list[NearbyPoiItem]:
        # Nominatim 不提供周边 POI 搜索，返回空列表
        logger.debug("Nominatim does not support nearby POI search, returning empty")
        return []


# ---------------------------------------------------------------------------
# 工厂：按 country 选择主引擎 + 备用
# ---------------------------------------------------------------------------


def _is_amap_primary(country: str | None) -> bool:
    """判断是否以高德为主引擎"""
    if not country:
        return True  # 默认中国大陆
    return country.upper() in _AMAP_PRIMARY_COUNTRIES


def get_primary_service(country: str | None = None) -> BaseGeocodingService:
    """根据国家/地区代码返回主地理编码服务"""
    if _is_amap_primary(country):
        return AmapGeocodingService()
    return GoogleGeocodingService()


def get_fallback_service() -> BaseGeocodingService:
    """返回备用地理编码服务（全球统一使用 Nominatim）"""
    return NominatimGeocodingService()


async def geocode_with_fallback(
    address: str,
    city: str | None = None,
    country: str | None = None,
) -> GeocodeResult:
    """地理编码：主引擎失败时自动降级到 Nominatim"""
    primary = get_primary_service(country)
    try:
        return await primary.geocode(address, city)
    except Exception as exc:
        logger.warning(
            "Primary geocoding failed for country=%s: %s, falling back to Nominatim",
            country,
            exc,
        )
        fallback = get_fallback_service()
        return await fallback.geocode(address, city)


async def search_nearby_with_fallback(
    location: str,
    keyword: str,
    country: str | None = None,
    *,
    radius: int | None = None,
    page_size: int | None = None,
    category: str = "周边设施",
) -> list[NearbyPoiItem]:
    """周边搜索：主引擎失败时降级（Nominatim 返回空列表）"""
    primary = get_primary_service(country)
    try:
        return await primary.search_nearby(
            location,
            keyword,
            radius=radius,
            page_size=page_size,
            category=category,
        )
    except Exception as exc:
        logger.warning(
            "Primary nearby search failed for country=%s: %s, falling back",
            country,
            exc,
        )
        fallback = get_fallback_service()
        return await fallback.search_nearby(
            location,
            keyword,
            radius=radius,
            page_size=page_size,
            category=category,
        )

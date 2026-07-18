# geocoding_service.py — 多引擎地理编码服务
# 中国大陆 → 高德地图（主），OSM Nominatim（备用）
# 海外 → Overpass / OSM（主），Nominatim（备用）

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 中国大陆使用高德作为主引擎
_AMAP_PRIMARY_COUNTRIES: frozenset[str] = frozenset({"CN"})


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
    lat: float | None = None   # 地图标记用
    lng: float | None = None

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

            # 解析高德 location 字段: "lng,lat"
            lat: float | None = None
            lng: float | None = None
            loc_str = item.get("location")
            if loc_str and "," in str(loc_str):
                try:
                    parts = str(loc_str).split(",")
                    lng = float(parts[0])
                    lat = float(parts[1])
                except (ValueError, IndexError):
                    pass

            results.append(
                NearbyPoiItem(
                    name=name,
                    distance=distance_text,
                    distance_meters=distance_meters,
                    category=category,
                    keyword=keyword,
                    address=item.get("address"),
                    lat=lat,
                    lng=lng,
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

            # 解析 Google location
            lat: float | None = None
            lng: float | None = None
            loc = geometry.get("location") if geometry else None
            if loc:
                try:
                    lat = float(loc.get("lat"))
                    lng = float(loc.get("lng"))
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
                    lat=lat,
                    lng=lng,
                )
            )

        items.sort(key=lambda poi: poi.distance_meters if poi.distance_meters is not None else 10**9)
        return items


# ---------------------------------------------------------------------------
# OSM Nominatim 引擎（全球备用引擎）
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Overpass API 引擎（免费、不限 Key，全球 POI 搜索）
# ---------------------------------------------------------------------------

# 将后端 NEARBY_SEARCH_PLAN 6 大分类映射到 Overpass 查询片段
_OVERPASS_CATEGORY_QUERIES: dict[str, str] = {
    "地铁站": """
        node["railway"="station"]["station"="subway"](around:{{radius}},{{lat}},{{lng}});
        node["station"="subway"](around:{{radius}},{{lat}},{{lng}});
        node["railway"="subway_entrance"](around:{{radius}},{{lat}},{{lng}});
    """,
    "公交站": """
        node["highway"="bus_stop"](around:{{radius}},{{lat}},{{lng}});
        node["amenity"="bus_station"](around:{{radius}},{{lat}},{{lng}});
    """,
    "火车站": """
        node["railway"="station"](around:{{radius}},{{lat}},{{lng}});
    """,
    "医院": """
        node["amenity"="hospital"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"="hospital"](around:{{radius}},{{lat}},{{lng}});
    """,
    "诊所": """
        node["amenity"="clinic"](around:{{radius}},{{lat}},{{lng}});
        node["amenity"="doctors"](around:{{radius}},{{lat}},{{lng}});
    """,
    "药店": """
        node["amenity"="pharmacy"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"="pharmacy"](around:{{radius}},{{lat}},{{lng}});
    """,
    "学校": """
        node["amenity"="school"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"="school"](around:{{radius}},{{lat}},{{lng}});
    """,
    "大学": """
        node["amenity"="university"](around:{{radius}},{{lat}},{{lng}});
        node["amenity"="college"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"="university"](around:{{radius}},{{lat}},{{lng}});
    """,
    "幼儿园": """
        node["amenity"="kindergarten"](around:{{radius}},{{lat}},{{lng}});
    """,
    "超市": """
        node["shop"~"supermarket|convenience"](around:{{radius}},{{lat}},{{lng}});
        way["shop"~"supermarket|convenience"](around:{{radius}},{{lat}},{{lng}});
    """,
    "商场": """
        node["shop"="mall"](around:{{radius}},{{lat}},{{lng}});
        node["shop"="department_store"](around:{{radius}},{{lat}},{{lng}});
        way["shop"="mall"](around:{{radius}},{{lat}},{{lng}});
    """,
    "便利店": """
        node["shop"="convenience"](around:{{radius}},{{lat}},{{lng}});
    """,
    "餐厅": """
        node["amenity"="restaurant"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"="restaurant"](around:{{radius}},{{lat}},{{lng}});
    """,
    "美食": """
        node["amenity"~"restaurant|fast_food|cafe"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"~"restaurant|fast_food|cafe"](around:{{radius}},{{lat}},{{lng}});
    """,
    "快餐": """
        node["amenity"="fast_food"](around:{{radius}},{{lat}},{{lng}});
    """,
    "银行": """
        node["amenity"="bank"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"="bank"](around:{{radius}},{{lat}},{{lng}});
    """,
    "菜市场": """
        node["amenity"="marketplace"](around:{{radius}},{{lat}},{{lng}});
        way["amenity"="marketplace"](around:{{radius}},{{lat}},{{lng}});
    """,
    "快递": """
        node["amenity"="post_office"](around:{{radius}},{{lat}},{{lng}});
        node["shop"="shipping"](around:{{radius}},{{lat}},{{lng}});
    """,
    "洗衣店": """
        node["shop"="laundry"](around:{{radius}},{{lat}},{{lng}});
    """,
}

# Overpass 镜像列表（按优先级依次尝试）
_OVERPASS_ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


class OverpassGeocodingService(BaseGeocodingService):
    """Overpass API 周边 POI 搜索（免费、无需 Key、全球覆盖）

    作为 Google Maps API Key 不可用时的降级方案。
    geocode() 不支持，仅提供 search_nearby()。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def geocode(self, address: str, city: str | None = None) -> GeocodeResult:
        raise RuntimeError("Overpass 不支持地理编码，请使用 Nominatim 降级")

    async def search_nearby(
        self,
        location: str,
        keyword: str,
        *,
        radius: int | None = None,
        page_size: int | None = None,
        category: str = "周边设施",
    ) -> list[NearbyPoiItem]:
        """通过 Overpass API 搜索周边 POI"""
        # 解析 location "lng,lat" 或 "lat,lng"
        parts = location.replace(" ", "").split(",")
        if len(parts) != 2:
            logger.warning("Overpass: invalid location format: %s", location)
            return []

        try:
            lat = float(parts[1]) if _is_likely_lng_lat(parts) else float(parts[0])
            lng = float(parts[0]) if _is_likely_lng_lat(parts) else float(parts[1])
        except (ValueError, IndexError):
            logger.warning("Overpass: cannot parse location: %s", location)
            return []

        query_fragment = _OVERPASS_CATEGORY_QUERIES.get(keyword)
        if not query_fragment:
            logger.debug("Overpass: no query mapping for keyword '%s'", keyword)
            return []

        search_radius = radius or self.settings.gm_nearby_radius_meters
        filled = query_fragment.replace("{{radius}}", str(search_radius)).replace(
            "{{lat}}", str(lat)
        ).replace("{{lng}}", str(lng))
        overpass_query = f"[out:json][timeout:15];({filled});out center 100;"

        timeout = httpx.Timeout(20.0)
        headers = {
            "User-Agent": "RentalHousingPlatform/1.0 (overpass fallback)",
            "Content-Type": "text/plain",
        }

        for endpoint in _OVERPASS_ENDPOINTS:
            try:
                async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                    resp = await client.post(endpoint, content=overpass_query)
                    resp.raise_for_status()
                    data = resp.json()

                elements = data.get("elements") or []
                if not elements:
                    continue  # 当前镜像返回空，尝试下一个

                return self._parse_overpass_elements(elements, keyword, category, lat, lng)

            except Exception as exc:
                logger.debug("Overpass endpoint %s failed: %s", endpoint, exc)
                continue

        logger.warning("Overpass: all endpoints failed for keyword '%s'", keyword)
        return []

    def _parse_overpass_elements(
        self,
        elements: list[dict],
        keyword: str,
        category: str,
        center_lat: float,
        center_lng: float,
    ) -> list[NearbyPoiItem]:
        """解析 Overpass 返回的 elements 为 NearbyPoiItem 列表"""
        from app.services.geo_utils import hav_distance_meters

        items: list[NearbyPoiItem] = []
        for el in elements:
            tags = el.get("tags") or {}
            # 优先取中文名 → 英文名 → 品牌名
            name = (
                tags.get("name:zh")
                or tags.get("name")
                or tags.get("name:en")
                or tags.get("official_name")
                or tags.get("brand")
                or tags.get("operator")
                or keyword
            ).strip()
            if not name:
                continue

            el_lat = el.get("lat") or (el.get("center", {}).get("lat") if isinstance(el.get("center"), dict) else None)
            el_lng = el.get("lon") or (el.get("center", {}).get("lon") if isinstance(el.get("center"), dict) else None)
            if el_lat is None or el_lng is None:
                continue

            distance_meters = int(hav_distance_meters(center_lat, center_lng, float(el_lat), float(el_lng)))
            if distance_meters >= 1000:
                distance_text = f"{distance_meters / 1000:.2f}km"
            else:
                distance_text = f"{distance_meters}m"

            items.append(
                NearbyPoiItem(
                    name=name,
                    distance=distance_text,
                    distance_meters=distance_meters,
                    category=category,
                    keyword=keyword,
                    lat=float(el_lat),
                    lng=float(el_lng),
                )
            )

        items.sort(key=lambda poi: poi.distance_meters if poi.distance_meters is not None else 10**9)
        return items


def _is_likely_lng_lat(parts: list[str]) -> bool:
    """判断是否 lng,lat（经度在前）。

    经度范围 [-180, 180]，纬度范围 [-90, 90]。
    利用绝对值 > 90 不可能为纬度的特点判断格式。
    当两部分都在 [-90, 90] 内时（如伦敦 -0.12，51.5），
    默认按 lng,lat 处理（内部 _resolve_location 的统一输出格式）。
    """
    try:
        first, second = float(parts[0]), float(parts[1])
    except (ValueError, IndexError):
        return True
    if abs(first) > 90:
        return True   # 第一部分不可能是纬度 → lng,lat
    if abs(second) > 90:
        return False  # 第二部分不可能是纬度 → lat,lng
    return True       # 两者都在 [-90, 90]：默认 lng,lat（内部格式）


# ---------------------------------------------------------------------------
# OSM Nominatim 引擎（全球备用引擎，仅 geocode）
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
    return OverpassGeocodingService()


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
    """周边搜索：主引擎 → Overpass → Nominatim（三级降级）"""
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
            "Primary nearby search failed for country=%s: %s, trying Overpass",
            country,
            exc,
        )

    # 一级降级：Overpass API（免费、全球、无需 Key）
    try:
        overpass = OverpassGeocodingService()
        results = await overpass.search_nearby(
            location,
            keyword,
            radius=radius,
            page_size=page_size,
            category=category,
        )
        if results:
            logger.info("Overpass fallback returned %d POIs for keyword '%s'", len(results), keyword)
            return results
    except Exception as exc:
        logger.debug("Overpass fallback also failed: %s", exc)

    # 二级降级：Nominatim（返回空列表，最终兜底）
    fallback = get_fallback_service()
    return await fallback.search_nearby(
        location,
        keyword,
        radius=radius,
        page_size=page_size,
        category=category,
    )

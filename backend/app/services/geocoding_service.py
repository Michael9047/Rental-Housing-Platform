from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class GeocodeResult:
    address: str
    latitude: float
    longitude: float
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


class AmapGeocodingService:
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
            latitude=float(latitude_str),
            longitude=float(longitude_str),
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

        pois = data.get("pois") or []
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

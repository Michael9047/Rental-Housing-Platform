"""StarRez HTTP 客户端 — 真实 API 调用 + Mock 模式"""
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.services.pms.base import PMSAuthError, PMSConnectionError

logger = logging.getLogger(__name__)

# ── StarRez API 默认配置 ────────────────────────────
DEFAULT_BASE_URL = "https://api.starrez.com/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_PAGE_SIZE = 100


# ═══════════════════════════════════════════════════════════════
# Mock 数据 — 模拟 StarRez 真实 JSON 结构
# ═══════════════════════════════════════════════════════════════

MOCK_SPACES = [
    {
        "id": "SR001",
        "name": "Ensuite Single Room 101",
        "type": "Ensuite Single",
        "description": (
            "Premium ensuite single room in shared cluster flat with 3 other students. "
            "Female only. £300 deposit required. Minimum stay one semester (Sep-Jan or Feb-Jun). "
            "Bills included. Study desk and high-speed WiFi provided."
        ),
        "status": "Occupied",
        "building": "Block A",
        "floor": 1,
        "area_sqm": 14.5,
        "max_occupancy": 1,
        "capacity": 1,
        "amenities": [
            "WiFi", "Desk", "Ensuite Bathroom", "Heating", "Laundry",
            "Common Room", "Bike Storage", "Security",
        ],
        "room_number": "101",
        "images": [
            "https://images.starrez.com/mock/ensuite-101-1.jpg",
            "https://images.starrez.com/mock/ensuite-101-2.jpg",
        ],
        "lease": {
            "rate_per_week": 185.00,
            "rate_per_month": None,
            "currency": "GBP",
            "start_date": "2026-09-15",
            "end_date": "2027-06-30",
            "min_stay_weeks": 16,
            "deposit_amount": 300,
            "deposit_weeks": None,
        },
        "address": {
            "line1": "Oxford Road, Manchester",
            "line2": None,
            "city": "Manchester",
            "postcode": "M13 9PL",
            "country": "United Kingdom",
        },
        "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
    },
    {
        "id": "SR002",
        "name": "Studio Apartment 205",
        "type": "Studio",
        "description": (
            "Self-contained studio apartment with private kitchen and bathroom. "
            "Suitable for single occupancy or couple. £500 deposit. "
            "Minimum stay full academic year (Sep-Jun). All bills included."
        ),
        "status": "Available",
        "building": "Block A",
        "floor": 2,
        "area_sqm": 24.0,
        "max_occupancy": 2,
        "capacity": 1,
        "amenities": [
            "WiFi", "Desk", "Private Bathroom", "Kitchen", "Heating",
            "TV", "Furnished", "Bills Included",
        ],
        "room_number": "205",
        "images": [
            "https://images.starrez.com/mock/studio-205-1.jpg",
            "https://images.starrez.com/mock/studio-205-2.jpg",
            "https://images.starrez.com/mock/studio-205-3.jpg",
        ],
        "lease": {
            "rate_per_week": 225.00,
            "rate_per_month": None,
            "currency": "GBP",
            "start_date": "2026-09-15",
            "end_date": "2027-06-30",
            "min_stay_weeks": 38,
            "deposit_amount": 500,
            "deposit_weeks": None,
        },
        "address": {
            "line1": "Oxford Road, Manchester",
            "line2": None,
            "city": "Manchester",
            "postcode": "M13 9PL",
            "country": "United Kingdom",
        },
        "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
    },
    {
        "id": "SR003",
        "name": "Twin Share Room 312",
        "type": "Twin Share",
        "description": (
            "Shared twin room in 4-person cluster flat. Two single beds, shared bathroom "
            "with one other room. Mixed gender flat. £250 deposit. "
            "Minimum stay one semester. No pets."
        ),
        "status": "Available",
        "building": "Block B",
        "floor": 3,
        "area_sqm": 18.0,
        "max_occupancy": 2,
        "capacity": 2,
        "amenities": [
            "WiFi", "Desk", "Shared Bathroom", "Shared Kitchen", "Heating",
            "Laundry", "Common Room", "Bike Storage",
        ],
        "room_number": "312",
        "images": [
            "https://images.starrez.com/mock/twin-312-1.jpg",
        ],
        "lease": {
            "rate_per_week": 145.00,
            "rate_per_month": None,
            "currency": "GBP",
            "start_date": "2026-09-15",
            "end_date": "2027-01-31",
            "min_stay_weeks": 16,
            "deposit_amount": 250,
            "deposit_weeks": None,
        },
        "address": {
            "line1": "Oxford Road, Manchester",
            "line2": None,
            "city": "Manchester",
            "postcode": "M13 9PL",
            "country": "United Kingdom",
        },
        "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
    },
    {
        "id": "SR004",
        "name": "One Bedroom Flat 401",
        "type": "One Bed Flat",
        "description": (
            "Spacious one bedroom flat with separate living area, private kitchen and bathroom. "
            "Ideal for couples or students wanting extra space. £600 deposit. "
            "Minimum stay full academic year. No pets, no smoking."
        ),
        "status": "Maintenance",
        "building": "Block B",
        "floor": 4,
        "area_sqm": 35.0,
        "max_occupancy": 2,
        "capacity": 1,
        "amenities": [
            "WiFi", "Desk", "Private Bathroom", "Kitchen", "Heating",
            "TV", "Furnished", "Bills Included", "Balcony", "Parking",
        ],
        "room_number": "401",
        "images": [
            "https://images.starrez.com/mock/flat-401-1.jpg",
            "https://images.starrez.com/mock/flat-401-2.jpg",
        ],
        "lease": {
            "rate_per_week": 275.00,
            "rate_per_month": None,
            "currency": "GBP",
            "start_date": "2026-09-15",
            "end_date": "2027-06-30",
            "min_stay_weeks": 38,
            "deposit_amount": 600,
            "deposit_weeks": 4,
        },
        "address": {
            "line1": "Oxford Road, Manchester",
            "line2": None,
            "city": "Manchester",
            "postcode": "M13 9PL",
            "country": "United Kingdom",
        },
        "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
    },
    {
        "id": "SR005",
        "name": "Ensuite Single Room 108",
        "type": "Ensuite Single",
        "description": (
            "Budget ensuite single in 6-person cluster flat. Mixed gender. "
            "£200 deposit. Minimum stay one semester. Basic furnishings. "
            "Bills not included (approx £60/month extra)."
        ),
        "status": "Available",
        "building": "Block A",
        "floor": 1,
        "area_sqm": 12.0,
        "max_occupancy": 1,
        "capacity": 1,
        "amenities": [
            "WiFi", "Desk", "Ensuite Bathroom", "Heating",
            "Laundry", "Common Room",
        ],
        "room_number": "108",
        "images": [
            "https://images.starrez.com/mock/ensuite-108-1.jpg",
        ],
        "lease": {
            "rate_per_week": 145.00,
            "rate_per_month": None,
            "currency": "GBP",
            "start_date": "2026-09-15",
            "end_date": "2027-01-31",
            "min_stay_weeks": 16,
            "deposit_amount": 200,
            "deposit_weeks": None,
        },
        "address": {
            "line1": "Oxford Road, Manchester",
            "line2": None,
            "city": "Manchester",
            "postcode": "M13 9PL",
            "country": "United Kingdom",
        },
        "coordinates": {"latitude": 53.4668, "longitude": -2.2334},
    },
]


# ═══════════════════════════════════════════════════════════════
# 客户端实现
# ═══════════════════════════════════════════════════════════════

class StarRezClient:
    """StarRez REST API 客户端

    Mock 模式（base_url 以 mock:// 开头）：返回内置模拟数据
    正式模式：真实 HTTP 调用 StarRez API
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._is_mock = base_url.startswith("mock://")
        self._http: httpx.AsyncClient | None = None

    # ── 公开接口 ──────────────────────────────────────────

    async def fetch_spaces(self, property_code: str | None = None) -> list[dict[str, Any]]:
        """拉取全量房源（spaces），自动处理分页"""
        if self._is_mock:
            return self._mock_fetch_spaces(property_code)
        return await self._api_fetch_spaces(property_code)

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ── Mock 实现 ──────────────────────────────────────────

    def _mock_fetch_spaces(self, property_code: str | None = None) -> list[dict[str, Any]]:
        logger.info("StarRez Mock: returning %d mock spaces", len(MOCK_SPACES))
        if property_code:
            return [s for s in MOCK_SPACES if s.get("building", "").startswith(property_code)]
        return list(MOCK_SPACES)

    # ── 真实 API 实现 ──────────────────────────────────────

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._http is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "RentalPlatform/1.0 (StarRez Connector)",
            }
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._http

    async def _api_fetch_spaces(self, property_code: str | None = None) -> list[dict[str, Any]]:
        """真实 StarRez API: GET /spaces?pageSize=100&pageNumber=N"""
        client = await self._ensure_client()
        all_spaces: list[dict[str, Any]] = []
        page = 1

        while True:
            params: dict[str, Any] = {"pageSize": DEFAULT_PAGE_SIZE, "pageNumber": page}
            if property_code:
                params["propertyCode"] = property_code

            try:
                response = await client.get("/spaces", params=params)
            except httpx.TimeoutException as exc:
                raise PMSConnectionError(f"StarRez API timeout on page {page}") from exc
            except httpx.ConnectError as exc:
                raise PMSConnectionError(f"StarRez API unreachable: {self.base_url}") from exc

            if response.status_code == 401:
                raise PMSAuthError("StarRez API authentication failed — check API key")
            if response.status_code == 429:
                logger.warning("StarRez rate limit hit on page %d, retrying...", page)
                import asyncio
                await asyncio.sleep(5)
                continue
            if not response.is_success:
                raise PMSConnectionError(
                    f"StarRez API error: {response.status_code} {response.text[:200]}"
                )

            data = response.json()
            spaces = data.get("spaces", data.get("results", []))
            all_spaces.extend(spaces)

            # StarRez 通常用 totalCount / pageCount 控制分页
            total = data.get("totalCount", 0)
            if len(all_spaces) >= total or len(spaces) < DEFAULT_PAGE_SIZE:
                break
            page += 1

        logger.info("StarRez API: fetched %d spaces across %d pages", len(all_spaces), page)
        return all_spaces

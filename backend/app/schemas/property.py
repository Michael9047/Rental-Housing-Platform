"""UnitType 房源卡 schema，并保留旧 Property 字段名作为前端兼容层。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class PropertySearchResult(BaseModel):
    """main canonical UnitType 字段 + 旧卡片兼容字段。

    ``id``/``unit_type_id`` 都是 UnitType.id；``institute_id`` 单独表示公寓。
    """
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: int = 0
    unit_type_id: int | None = None
    name: str = ""
    base_rent: float | None = None
    institute_address: str | None = None
    has_vacancy: bool = False
    available_count: int = 0
    total_count: int = 0
    landlord_id: int = 0
    title: str = ""
    description: str | None = None
    address: str | None = None
    country: str | None = None
    city: str | None = None
    district: str | None = None
    price_monthly: Decimal | float | None = None
    area_sqm: Decimal | float | None = None
    bedrooms: int = 0
    bathrooms: int = 0
    property_type: str | None = None
    status: str = "available"
    currency: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    images: list[Any] = []
    image_urls: list[str] = []
    institute_id: int | None = None
    institute_name: str | None = None
    amenities: list[str] | None = None
    available_from: str | None = None
    min_stay_months: int | None = None
    special_offer: str | None = None


class PropertyCreate(BaseModel):
    """兼容占位 — 接受任意字段，model_dump 返回所有传入值。"""
    model_config = ConfigDict(extra="allow")

    institute_id: int | None = None
    title: str | None = None
    description: str | None = None


class PropertyUpdate(BaseModel):
    """兼容占位 — model_dump(exclude_unset=True) 返回传入字段。"""
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    version: int | None = None

"""Property 相关 Schema 兼容占位 — Property 模型已删除，Phase 3 重写后会删除此文件。

提供 PropertySearchResult、PropertyCreate、PropertyUpdate 的最小占位定义，
让旧代码能 import 不报错。运行时行为：所有方法返回空/默认值。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class PropertySearchResult(BaseModel):
    """兼容占位 — Property 模型已删除。"""
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: int = 0
    landlord_id: int = 0
    title: str = ""
    description: str | None = None
    address: str | None = None
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
    institute_id: int | None = None
    institute_name: str | None = None

<<<<<<< HEAD
class PropertyCreate(PropertyBase):
    landlord_id: int
    image_urls: list[str] | None = None


class PropertyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    address: str | None = Field(default=None, min_length=1, max_length=300)
    district: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    price_monthly: Decimal | None = Field(default=None, ge=0)
    area_sqm: Decimal | None = Field(default=None, gt=0)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    property_type: PropertyType | None = None
    status: PropertyStatus | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    deposit_amount: int | None = None
    service_fee_rate: float | None = None
    room_number: str | None = Field(default=None, max_length=20)
    floor: int | None = Field(default=None, ge=0)
    # ── 新增字段 ──
    amenities: list[str] | None = None
    available_from: date | None = None
    min_stay_months: int | None = Field(default=None, ge=1)
    deposit_type: DepositType | None = None
    version: int | None = Field(default=None, ge=1)


class PropertyRead(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    landlord_id: int
    business_id: str | None = None
    institute_name: str | None = None
    version: int = 1
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    images: list[PropertyImageRead] = []

    @property
    def primary_image_url(self) -> str | None:
        for img in self.images:
            if img.is_primary:
                return f"/api/v1/uploads/{img.filename}"
        return None


class PropertySearchResult(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    landlord_id: int
    business_id: str | None = None
    institute_name: str | None = None
    created_at: datetime
    updated_at: datetime
    images: list[PropertyImageRead] = []
    similarity: float | None = None

    @property
    def primary_image_url(self) -> str | None:
        for img in self.images:
            if img.is_primary:
                return f"/api/v1/uploads/{img.filename}"
        return None


# ── 分页响应 ──
class PropertyListResponse(BaseModel):
    items: list[PropertyRead]
    total: int
    page: int
    page_size: int
    total_pages: int
=======

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
>>>>>>> merge/pr33-pr35

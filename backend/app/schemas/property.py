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

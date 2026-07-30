"""户型 Pydantic 模式（稳定版）"""
from datetime import date, datetime
from pydantic import BaseModel, Field


class UnitTypeCreate(BaseModel):
    """创建户型"""
    institute_id: int = Field(..., description="所属公寓ID")
    name: str = Field(..., min_length=1, max_length=100)
    bedrooms: int = Field(default=0, ge=0)
    bathrooms: int = Field(default=0, ge=0)
    hall_count: int = Field(default=0, ge=0)
    area_sqm: float | None = Field(default=None, gt=0)
    base_rent: float = Field(..., ge=0)
    deposit_amount: float | None = None
    deposit_type: str | None = None
    lease_start: str | None = None
    lease_start_date: date | None = None
    lease_end: str | None = None
    lease_end_date: date | None = None
    rental_requirements: str | None = None  # 选填，替代起止租期
    currency: str | None = None
    special_offer: str | None = None
    floor_pricing: list[dict] | None = None
    amenities: list[str] | None = None
    image_urls: list[str] | None = None  # 临时上传的图片 URL 列表
    description: str | None = Field(default=None, max_length=2000)
    available_from: date | None = None
    min_stay_months: int = Field(default=3, ge=1)
    status: str = Field(default="available")


class UnitTypeUpdate(BaseModel):
    """更新户型 — 所有字段可选"""
    institute_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    hall_count: int | None = Field(default=None, ge=0)
    area_sqm: float | None = Field(default=None, gt=0)
    base_rent: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = None
    deposit_type: str | None = None
    lease_start: str | None = None
    lease_start_date: date | None = None
    lease_end: str | None = None
    lease_end_date: date | None = None
    rental_requirements: str | None = None
    currency: str | None = None
    special_offer: str | None = None
    floor_pricing: list[dict] | None = None
    amenities: list[str] | None = None
    image_urls: list[str] | None = None
    description: str | None = Field(default=None, max_length=2000)
    available_from: date | None = None
    min_stay_months: int | None = Field(default=None, ge=1)
    status: str | None = None


class UnitTypeRead(BaseModel):
    """户型响应"""
    id: int
    business_id: str | None = None
    uuid: str | None = None
    institute_id: int
    institute_name: str | None = None
    institute_business_id: str | None = None
    name: str
    bedrooms: int
    bathrooms: int
    hall_count: int
    area_sqm: float | None = None
    base_rent: float
    deposit_amount: float | None = None
    deposit_type: str | None = None
    lease_start: str | None = None
    lease_start_date: date | None = None
    lease_end: str | None = None
    lease_end_date: date | None = None
    rental_requirements: str | None = None
    currency: str | None = None
    special_offer: str | None = None
    floor_pricing: list[dict] | None = None
    amenities: list[str] | None = None
    description: str | None = None
    available_from: date | None = None
    min_stay_months: int
    status: str
    room_count: int = 0
    images: list[dict] = []
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UnitTypeListResponse(BaseModel):
    items: list[UnitTypeRead]
    total: int
    page: int
    page_size: int
    total_pages: int

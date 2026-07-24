"""户型 Pydantic 模式"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class UnitTypeCreate(BaseModel):
    """创建户型"""
    institute_id: int = Field(..., description="所属公寓ID")
    name: str = Field(..., min_length=1, max_length=100)
    bedrooms: int = Field(default=0, ge=0, description="卧室数量")
    bathrooms: int = Field(default=1, ge=0, description="卫生间数量")
    hall_count: int = Field(default=0, ge=0, description="厅数量")
    area_sqm: Decimal | None = Field(default=None, gt=0, description="面积(㎡)")
    base_rent: Decimal = Field(..., ge=0, description="标准月租金")
    deposit_amount: int | None = Field(default=None, description="押金")
    deposit_type: str | None = Field(default=None, description="押金类型")
    lease_start: str | None = Field(default=None, description="起租时间(自由文本)")
    lease_end: str | None = Field(default=None, description="止租时间(自由文本)")
    currency: str | None = Field(default=None, description="货币代码(CNY/USD/GBP等)")
    special_offer: str | None = Field(default=None, description="专属优惠(自由文本)")
    floor_pricing: list[dict] | None = Field(default=None, description="楼层差异化加价")
    amenities: list[str] | None = Field(default=None, description="配套设施")
    image_urls: list[str] | None = Field(default=None, description="户型平面图/效果图URL列表")
    description: str | None = Field(default=None, max_length=2000)
    available_from: date | None = Field(default=None, description="可入住日期")
    min_stay_months: int = Field(default=3, ge=1, description="最短租期(月)")
    status: str = Field(default="available")


class UnitTypeUpdate(BaseModel):
    """更新户型 — 所有字段可选"""
    institute_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    hall_count: int | None = Field(default=None, ge=0)
    area_sqm: Decimal | None = Field(default=None, gt=0)
    base_rent: Decimal | None = Field(default=None, ge=0)
    deposit_amount: int | None = None
    deposit_type: str | None = None
    lease_start: str | None = None
    lease_end: str | None = None
    floor_pricing: list[dict] | None = None
    amenities: list[str] | None = None
    image_urls: list[str] | None = None
    description: str | None = Field(default=None, max_length=2000)
    available_from: date | None = None
    min_stay_months: int | None = Field(default=None, ge=1)
    status: str | None = None
    currency: str | None = None
    special_offer: str | None = None


class UnitTypeRead(BaseModel):
    """户型响应"""
    id: int
    institute_id: int
    institute_name: str | None = None
    institute_business_id: str | None = None
    name: str
    bedrooms: int
    bathrooms: int
    hall_count: int
    area_sqm: Decimal | None = None
    base_rent: Decimal
    deposit_amount: int | None = None
    deposit_type: str | None = None
    lease_start: str | None = None
    lease_end: str | None = None
    currency: str | None = None
    special_offer: str | None = None
    floor_pricing: list[dict] | None = None
    amenities: list[str] | None = None
    image_urls: list[str] | None = None
    description: str | None = None
    available_from: date | None = None
    min_stay_months: int
    status: str
    room_count: int = 0
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

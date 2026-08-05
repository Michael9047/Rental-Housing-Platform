"""户型 Pydantic 模式"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class UnitTypeCreate(BaseModel):
    """创建户型"""
    institute_id: int = Field(..., description="所属公寓ID")
    name: str = Field(..., min_length=1, max_length=100)
    property_type: str | None = Field(default=None, description="户型分类: studio/ensuite/1bed/2bed/3bed/4bed/5bed+/shared")
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
    has_vacancy: bool = Field(default=True, description="是否有空房")
    total_count: int = Field(default=1, ge=0, description="该户型总套数")
    available_count: int = Field(default=1, ge=0, description="剩余可租套数")
    status: str = Field(default="available")


class UnitTypeUpdate(BaseModel):
    """更新户型 — 所有字段可选"""
    institute_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    property_type: str | None = None
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
    has_vacancy: bool | None = None
    total_count: int | None = Field(default=None, ge=0)
    available_count: int | None = Field(default=None, ge=0)
    status: str | None = None
    currency: str | None = None
    special_offer: str | None = None


class UnitTypeRead(BaseModel):
    """户型响应 — 整并 Institute 字段，作为前端主要展示实体"""
    # ── UnitType 自身 ──
    id: int
    business_id: str | None = None
    uuid: str | None = None
    institute_id: int
    name: str
    property_type: str | None = None
    bedrooms: int
    bathrooms: int
    hall_count: int
    area_sqm: Decimal | None = None
    base_rent: Decimal
    deposit_amount: int | None = None
    deposit_type: str | None = None
    lease_start: str | None = None
    lease_end: str | None = None
    lease_start_date: date | None = None
    lease_end_date: date | None = None
    currency: str | None = None
    rent_period: str = "monthly"
    special_offer: str | None = None
    floor_pricing: list[dict] | None = None
    amenities: list[str] | None = None
    image_urls: list[str] | None = None
    description: str | None = None
    available_from: date | None = None
    min_stay_months: int
    has_vacancy: bool = True
    total_count: int = 1
    available_count: int = 1
    status: str
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # ── Institute 继承字段 ──
    institute_name: str | None = None
    institute_business_id: str | None = None
    institute_address: str | None = None
    country: str | None = None
    city: str | None = None
    district: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    logo_url: str | None = None
    female_only: bool = False
    couples_allowed: bool = False
    building_type: str | None = None
    total_floors: int | None = None
    year_built: int | None = None
    has_elevator: bool = False
    website_url: str | None = None

    model_config = {"from_attributes": True}


class UnitTypeListResponse(BaseModel):
    items: list[UnitTypeRead]
    total: int
    page: int
    page_size: int
    total_pages: int

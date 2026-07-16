from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.property import DepositType, PropertyStatus, PropertyType
from app.schemas.property_image import PropertyImageRead


class PropertyBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    address: str = Field(min_length=1, max_length=300)
    district: str = Field(min_length=1, max_length=100)
    price_monthly: Decimal = Field(ge=0)
    country: str = Field(default="CN", min_length=2, max_length=2)
    area_sqm: Decimal | None = Field(default=None, gt=0)
    bedrooms: int = Field(default=0, ge=0)
    bathrooms: int = Field(default=0, ge=0)
    property_type: PropertyType = PropertyType.apartment
    status: PropertyStatus = PropertyStatus.available
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    deposit_amount: int | None = None
    service_fee_rate: float | None = None
    room_number: str | None = Field(default=None, max_length=20)
    floor: int | None = Field(default=None, ge=0)
    # ── 新增字段 ──
    amenities: list[str] | None = None
    available_from: date | None = None
    min_stay_months: int = Field(default=3, ge=1)
    deposit_type: DepositType | None = None


class PropertyCreate(PropertyBase):
    landlord_id: int
    # 与 ORM 模型一致（Property.institute_id 为 nullable，ondelete="SET NULL"）：
    # 机构关联是可选的，不是所有房东都挂靠机构
    institute_id: int | None = None
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
    institute_id: int | None = None
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
    institute_id: int | None = None
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
    institute_id: int | None = None
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

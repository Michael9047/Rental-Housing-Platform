from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.property import RoomStatus as PropertyStatus
from app.models.unit_type import DepositType
# 以下枚举已废弃，保留兼容定义
import enum as _enum
class PropertyType(str, _enum.Enum):
    studio = "studio"      # 单间/开间
    one_bed = "1-bed"      # 一室一厅
    two_bed = "2-bed"      # 两室及以上
    shared = "shared"      # 合租单间
    house = "house"        # 独栋/联排别墅
class RentType(str, _enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"
from app.schemas.property_image import PropertyImageRead
class PropertyBase(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    address: str | None = Field(default=None, max_length=500)
    district: str | None = Field(default=None, max_length=100)
    price_monthly: Decimal | None = None
    country: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=3)
    area_sqm: Decimal | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    property_type: str | None = None
    status: str = "available"
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    deposit_amount: int | None = None
    service_fee_rate: float | None = None
    min_lease_months: int | None = None
    max_lease_months: int | None = None
    rent_type: str | None = None
    room_number: str | None = None
    floor: int | None = None
    # 新增字段
    amenities: list[str] | None = None
    available_from: date | None = None
    min_stay_months: int | None = None
    deposit_type: str | None = None

class PropertyCreate(PropertyBase):
    landlord_id: int
    institute_id: int
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

"""已废弃 — RoomType 表已删除，已被 UnitType 替代。保留兼容导入。"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel
import enum


class RoomTypeEnum(str, enum.Enum):
    studio = "studio"
    ensuite = "ensuite"
    one_bed = "1bed"
    two_bed = "2bed"
    three_bed_plus = "3bed+"
    shared = "shared"


class RoomTypeStatus(str, enum.Enum):
    available = "available"
    rented = "rented"
    maintenance = "maintenance"


class DepositType(str, enum.Enum):
    one_month = "one_month"
    one_three = "one_three"
    two_month = "two_month"
    three_month = "three_month"
    half_month = "half_month"
    free = "free"
    custom = "custom"


class RoomTypeBase(BaseModel):
    name: str = ""
    room_type: RoomTypeEnum = RoomTypeEnum.studio
    bedrooms: int = 0
    bathrooms: int = 1
    price_monthly: Decimal = Decimal("0")
    area_sqm: Decimal | None = None
    floor: int | None = None
    available_count: int = 1
    available_from: date | None = None
    min_stay_months: int = 3
    deposit_amount: int | None = None
    deposit_type: str | None = None
    amenities: list[str] | None = None
    description: str | None = None
    status: str = "available"


class RoomTypeCreate(RoomTypeBase):
    pass


class RoomTypeUpdate(RoomTypeBase):
    pass


class RoomTypeRead(RoomTypeBase):
    id: int = 0
    property_id: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

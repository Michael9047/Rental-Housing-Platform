"""房型 Pydantic Schema"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.room_type import DepositType, RoomTypeEnum, RoomTypeStatus


class RoomTypeBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    room_type: RoomTypeEnum = RoomTypeEnum.studio
    bedrooms: int = Field(default=0, ge=0)
    bathrooms: int = Field(default=1, ge=0)
    price_monthly: Decimal = Field(ge=0)
    area_sqm: Decimal | None = Field(default=None, gt=0)
    floor: int | None = None
    available_count: int = Field(default=1, ge=0)
    available_from: date | None = None
    min_stay_months: int = Field(default=3, ge=1)
    deposit_amount: int | None = None
    deposit_type: DepositType | None = None
    amenities: list[str] | None = None
    description: str | None = None
    status: RoomTypeStatus = RoomTypeStatus.available


class RoomTypeCreate(RoomTypeBase):
    pass


class RoomTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    room_type: RoomTypeEnum | None = None
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    price_monthly: Decimal | None = Field(default=None, ge=0)
    area_sqm: Decimal | None = Field(default=None, gt=0)
    floor: int | None = None
    available_count: int | None = Field(default=None, ge=0)
    available_from: date | None = None
    min_stay_months: int | None = Field(default=None, ge=1)
    deposit_amount: int | None = None
    deposit_type: DepositType | None = None
    amenities: list[str] | None = None
    description: str | None = None
    status: RoomTypeStatus | None = None


class RoomTypeRead(RoomTypeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    created_at: datetime
    updated_at: datetime

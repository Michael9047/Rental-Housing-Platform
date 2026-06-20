from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.property import PropertyStatus, PropertyType


class PropertyBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    address: str = Field(min_length=1, max_length=300)
    district: str = Field(min_length=1, max_length=100)
    price_monthly: Decimal = Field(ge=0)
    area_sqm: Decimal | None = Field(default=None, gt=0)
    bedrooms: int = Field(default=0, ge=0)
    bathrooms: int = Field(default=0, ge=0)
    property_type: PropertyType = PropertyType.apartment
    status: PropertyStatus = PropertyStatus.available
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)


class PropertyCreate(PropertyBase):
    landlord_id: int


class PropertyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    address: str | None = Field(default=None, min_length=1, max_length=300)
    district: str | None = Field(default=None, min_length=1, max_length=100)
    price_monthly: Decimal | None = Field(default=None, ge=0)
    area_sqm: Decimal | None = Field(default=None, gt=0)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    property_type: PropertyType | None = None
    status: PropertyStatus | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)


class PropertyRead(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    landlord_id: int
    created_at: datetime
    updated_at: datetime



class PropertySearchResult(PropertyRead):
    similarity: float | None = None
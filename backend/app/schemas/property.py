from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.property_image import PropertyImageRead

from app.models.property import PropertyStatus, PropertyType, RentType


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
    min_lease_months: int = 12
    max_lease_months: int | None = 60
    rent_type: RentType = RentType.monthly

class PropertyCreate(PropertyBase):
    landlord_id: int


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


class PropertyRead(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    landlord_id: int
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

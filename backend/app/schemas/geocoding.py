from decimal import Decimal

from pydantic import BaseModel, Field


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=1, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)


class GeocodeResponse(BaseModel):
    address: str
    latitude: Decimal
    longitude: Decimal
    formatted_address: str | None = None
    level: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None

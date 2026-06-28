from pydantic import BaseModel, Field


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=1, max_length=300)
    city: str | None = Field(default=None, max_length=100)


class GeocodeResponse(BaseModel):
    address: str
    latitude: float
    longitude: float
    formatted_address: str | None = None
    level: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    property_id: int
    message: str | None = Field(default=None, max_length=2000)
    scheduled_date: str | None = Field(default=None, max_length=32)


class BookingUpdate(BaseModel):
    status: BookingStatus


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    property_id: int
    landlord_id: int
    status: BookingStatus
    message: str | None
    scheduled_date: str | None
    created_at: datetime
    updated_at: datetime

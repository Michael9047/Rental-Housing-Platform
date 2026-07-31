from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    unit_type_id: int
    institute_id: int | None = None
    tenant_id: int | None = None
    message: str | None = Field(default=None, max_length=2000)
    scheduled_date: str | None = Field(default=None, max_length=32)
    room_number: str | None = Field(default=None, max_length=20)
    deposit_amount: int | None = None
    service_fee: int | None = None
    lease_months: int | None = None
    total_rent: int | None = None
    application_data: dict | None = None


class BookingUpdate(BaseModel):
    status: BookingStatus | None = None
    deposit_status: str | None = None
    payment_transaction_id: str | None = None
    room_number: str | None = None
    contract_start: date | None = None
    contract_end: date | None = None


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    tenant_id: int | None = None
    unit_type_id: int | None = None
    institute_id: int | None = None
    bm_id: int | None = None
    room_number: str | None = None
    status: BookingStatus
    message: str | None = None
    scheduled_date: str | None = None
    contract_start: date | None = None
    contract_end: date | None = None
    deposit_amount: int | None = None
    service_fee: int | None = None
    deposit_status: str | None = None
    payment_transaction_id: str | None = None
    lease_months: int | None = None
    total_rent: int | None = None
    application_data: dict | None = None
    created_at: datetime
    updated_at: datetime
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    property_id: int
    message: str | None = Field(default=None, max_length=2000)
    scheduled_date: str | None = Field(default=None, max_length=32)


class BookingUpdate(BaseModel):
    status: BookingStatus | None = None
    deposit_status: str | None = None
    payment_transaction_id: str | None = None


class BookingContractInfoUpdate(BaseModel):
    contract_real_name: str = Field(min_length=1, max_length=100)
    contract_id_card_no: str = Field(min_length=6, max_length=32)
    contract_phone: str = Field(min_length=6, max_length=32)
    lease_start_date: str = Field(min_length=1, max_length=32)
    lease_end_date: str = Field(min_length=1, max_length=32)
    contract_extra_terms: str | None = Field(default=None, max_length=2000)


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    property_id: int
    landlord_id: int
    status: BookingStatus
    message: str | None
    scheduled_date: str | None
    deposit_amount: int | None = None
    service_fee: int | None = None
    deposit_status: str | None = None
    payment_transaction_id: str | None = None
    contract_real_name: str | None = None
    contract_id_card_no: str | None = None
    contract_phone: str | None = None
    lease_start_date: str | None = None
    lease_end_date: str | None = None
    contract_extra_terms: str | None = None
    contract_info_status: str = "missing"
    contract_landlord_confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContractCreate(BaseModel):
    booking_id: int


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: int
    tenant_id: int
    property_id: int
    template_name: str
    agreement_number: str | None = None
    version: int = 1
    template_version: str = "2026.1"
    content_hash: str | None = None
    snapshot: dict[str, Any] | None = None
    generated_at: datetime | None = None
    content: str
    status: str
    signed_at: datetime | None = None
    file_path: str | None = None
    pdf_status: str = "not_generated"
    created_at: datetime
    updated_at: datetime


class SignaturePoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    pressure: float = Field(default=0.5, ge=0, le=1)


class ContractSignCreate(BaseModel):
    agreement_version: int = Field(ge=1)
    agreement_content_hash: str = Field(min_length=64, max_length=64)
    tenant_name: str = Field(min_length=1, max_length=200)
    consent_text_version: str = Field(min_length=1, max_length=32)
    idempotency_key: str = Field(min_length=8, max_length=100)
    strokes: list[list[SignaturePoint]] = Field(min_length=1, max_length=100)
    name_confirmed: bool
    electronic_signature_consent: bool


class ContractSignatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agreement_id: str
    agreement_version: int
    agreement_content_hash: str
    tenant_user_id: int
    tenant_name: str
    signed_at: datetime
    property_timezone: str
    consent_text_version: str
    signature_hash: str
    pdf_status: str = "pending"


class TenantContractListItem(BaseModel):
    agreement_id: str
    agreement_number: str
    agreement_version: int
    agreement_content_hash: str
    order_id: str
    booking_id: int
    property_id: int
    tenant_user_id: int
    signed_at: datetime
    lease_start_date: str | None
    lease_end_date: str | None
    lease_months: int | None
    property_timezone: str
    property_name: str
    property_address: str
    property_image_url: str | None
    payment_status: str
    booking_status: str
    reservation_status: str
    agreement_status: str
    category: str
    category_label: str
    status_labels: list[str]
    invalid_reason: str | None = None
    settlement_currency: str | None = None
    settlement_amount_minor: int | None = None
    payment_expires_at: datetime | None = None
    remaining_payment_seconds: int | None = None
    remaining_contract_days: int | None = None
    can_pay: bool = False
    waiting_for_move_in: bool = False
    signed_pdf_available: bool = False


class TenantContractDetail(TenantContractListItem):
    content: str
    snapshot: dict[str, Any]
    signature_url: str


class TenantContractListResponse(BaseModel):
    items: list[TenantContractListItem]
    total: int

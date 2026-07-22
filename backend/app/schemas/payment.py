"""支付订单请求和只读响应模型。"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.services.payment_provider import PaymentMethod


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: int
    payment_method: PaymentMethod = PaymentMethod.CARD_CHECKOUT


class PaymentMethodAvailability(BaseModel):
    method: PaymentMethod
    available: bool
    test_mode: bool
    reason: str | None = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; order_id: str; payment_attempt_id: str; booking_id: int; user_id: int; amount: int
    status: str; payment_method: str; provider: str
    order_status: str | None = None
    settlement_currency: str; settlement_amount_minor: int
    cny_reference_amount_minor: int; property_currency: str
    exchange_rate: Decimal; exchange_rate_source: str
    exchange_rate_timestamp: datetime; expires_at: datetime
    checkout_url: str | None = None; snapshot: dict = Field(default_factory=dict)
    transaction_id: str | None = None; paid_at: datetime | None = None
    created_at: datetime; updated_at: datetime


class PaymentResultResponse(PaymentResponse):
    """支付结果页所需的后端可信订单摘要。"""
    property_image_url: str | None = None
    booking_created_at: datetime
    status_updated_at: datetime
    failure_reason: str | None = None


class TenantOrderListItem(BaseModel):
    booking_id: int
    order_id: str
    agreement_id: str
    agreement_number: str
    property_id: int
    property_name: str
    property_image_url: str | None = None
    property_city: str
    property_address: str
    lease_start_date: str | None = None
    lease_end_date: str | None = None
    lease_months: int | None = None
    settlement_currency: str
    settlement_amount_minor: int
    cny_reference_amount_minor: int
    property_currency: str
    property_amount_minor: int
    order_status: str
    payment_status: str
    booking_status: str
    status_label: str
    created_at: datetime
    expires_at: datetime
    remaining_payment_seconds: int
    can_pay: bool
    payment_action_label: str | None = None
    failure_reason: str | None = None


class TenantOrderDetail(TenantOrderListItem):
    applicant_name: str
    applicant_phone_masked: str | None = None
    applicant_email_masked: str | None = None
    property_type: str
    property_country: str
    property_description: str | None = None
    monthly_rent_minor: int
    deposit_amount_minor: int
    service_fee_amount_minor: int
    tax_amount_minor: int
    exchange_rate: Decimal
    exchange_rate_source: str
    exchange_rate_timestamp: datetime
    status_updated_at: datetime
    paid_at: datetime | None = None
    transaction_id_masked: str | None = None
    webhook_confirmed: bool = False
    amounts_verified: bool = False
    inventory_reserved: bool = False


class PaymentEligibilityResponse(BaseModel):
    booking_id: int
    can_pay: bool
    order_status: str
    payment_status: str
    expires_at: datetime
    reason: str | None = None
    payment_id: str | None = None


class TenantOrderListResponse(BaseModel):
    items: list[TenantOrderListItem]
    total: int

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    booking_id: int
    amount: int


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: int
    user_id: int
    amount: int
    out_trade_no: str | None = None
    prepay_id: str | None = None
    transaction_id: str | None = None
    status: str
    payment_method: str
    trade_state: str | None = None
    trade_state_desc: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

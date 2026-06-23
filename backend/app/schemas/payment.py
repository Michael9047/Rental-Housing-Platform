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
    transaction_id: str | None = None
    status: str
    payment_method: str
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
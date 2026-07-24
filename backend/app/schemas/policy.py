"""预订政策确认 schema。"""
from datetime import date

from pydantic import BaseModel


class PolicyAcceptanceItem(BaseModel):
    key: str
    version: int
    content_hash: str


class BookingConfirmationCreate(BaseModel):
    property_id: int
    move_in_date: date
    lease_months: int
    policy_acceptances: list[PolicyAcceptanceItem]


class BookingConfirmationRead(BaseModel):
    booking_id: int
    consent_count: int

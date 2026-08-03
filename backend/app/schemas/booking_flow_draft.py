"""预订流程草稿 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookingPersonalInfoData(BaseModel):
    chinese_name: str | None = None
    given_name_pinyin: str | None = None
    surname_pinyin: str | None = None
    birth_date: str | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    nationality: str | None = None
    school_name: str | None = None
    enrollment_grade: str | None = None
    major_english: str | None = None
    region: str | None = None
    address_detail: str | None = None
    postal_code: str | None = None


class BookingEmergencyContactData(BaseModel):
    chinese_name: str | None = None
    given_name_pinyin: str | None = None
    surname_pinyin: str | None = None
    relation: str | None = None
    birth_date: str | None = None
    phone: str | None = None
    email: str | None = None
    gender: str | None = None
    region: str | None = None
    address_detail: str | None = None
    postal_code: str | None = None
    consultant_id: str | None = None


class BookingFlowDraftUpdate(BaseModel):
    move_in_date: str | None = None
    lease_months: int | None = None
    current_step: str | None = None
    personal_info: BookingPersonalInfoData | None = None
    emergency_contact: BookingEmergencyContactData | None = None


class BookingFlowDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    unit_type_id: int
    current_step: str
    move_in_date: str | None = None
    lease_months: int | None = None
    personal_info: dict | None = None
    emergency_contact: dict | None = None
    created_at: datetime
    updated_at: datetime

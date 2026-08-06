"""预订流程草稿 schema。"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class BookingPersonalInfoData(BaseModel):
    chinese_name: str | None = None
    given_name_pinyin: str | None = None
    surname_pinyin: str | None = None
    birth_date: date | None = None
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
    address_line: str | None = None
    phone_country_code: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    level1_code: str | None = None
    level1_name: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    district_code: str | None = None
    district_name: str | None = None


class BookingEmergencyContactData(BaseModel):
    chinese_name: str | None = None
    relationship: str | None = None
    given_name_pinyin: str | None = None
    surname_pinyin: str | None = None
    relation: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    gender: str | None = None
    region: str | None = None
    address_detail: str | None = None
    postal_code: str | None = None
    consultant_id: str | None = None
    address_line: str | None = None
    phone_country_code: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    level1_code: str | None = None
    level1_name: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    district_code: str | None = None
    district_name: str | None = None
    same_as_personal_address: bool | None = None


class BookingFlowDraftUpdate(BaseModel):
    move_in_date: date | str | None = None
    lease_months: int | None = None
    current_step: Literal["move_in_date", "lease_term", "personal_info", "emergency_contact", "review"] | None = None
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

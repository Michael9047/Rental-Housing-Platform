"""预订紧急联系人校验 schema。"""
from pydantic import BaseModel


class BookingEmergencyContactValidation(BaseModel):
    """紧急联系人校验请求。"""
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


class BookingEmergencyContactValidationRead(BaseModel):
    valid: bool = True

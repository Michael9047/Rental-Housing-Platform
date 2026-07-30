"""预订个人信息校验 schema。"""
from pydantic import BaseModel


class BookingPersonalInfoValidation(BaseModel):
    """个人信息校验请求。"""
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


class BookingPersonalInfoValidationRead(BaseModel):
    valid: bool = True

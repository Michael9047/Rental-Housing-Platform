"""预订个人信息校验 schema。"""
import re
from datetime import date

from pydantic import BaseModel, field_validator


class BookingPersonalInfoValidation(BaseModel):
    """个人信息校验请求。"""
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

    @field_validator("surname_pinyin", "given_name_pinyin")
    @classmethod
    def normalize_pinyin(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.upper()
        if not re.fullmatch(r"[A-Z -]+", normalized):
            raise ValueError("拼音仅支持英文大写字母、空格和连字符")
        return normalized

    @field_validator("birth_date")
    @classmethod
    def validate_age(cls, value: date | None) -> date | None:
        if value is None:
            return value
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise ValueError("申请人须年满 18 周岁")
        if age > 100:
            raise ValueError("申请人年龄不能超过 100 周岁")
        return value


class BookingPersonalInfoValidationRead(BaseModel):
    valid: bool = True

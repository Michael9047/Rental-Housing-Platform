"""租客档案 & 订单 Pydantic 模式"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ── 租客档案（匹配 Tenant 模型全字段）──

class TenantCreate(BaseModel):
    """创建租客档案 — 全部可选以便分步填写"""
    label: str | None = Field(default=None, max_length=100, description="标签，如'本人'/'室友A'")
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
    enrollment_level: str | None = None
    enrollment_term: str | None = None
    student_classification: str | None = None
    preferred_name: str | None = None
    is_international: bool = True
    visa_type: str | None = None
    visa_expiry: date | None = None
    citizenship_country: str | None = None
    disability_needs: str | None = None
    dietary_needs: str | None = None
    gender_identity: str | None = None


class TenantUpdate(BaseModel):
    """更新租客档案 — 全部可选"""
    label: str | None = Field(default=None, max_length=100)
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
    enrollment_level: str | None = None
    enrollment_term: str | None = None
    student_classification: str | None = None
    preferred_name: str | None = None
    is_international: bool | None = None
    visa_type: str | None = None
    visa_expiry: date | None = None
    citizenship_country: str | None = None
    disability_needs: str | None = None
    dietary_needs: str | None = None
    gender_identity: str | None = None


class TenantRead(BaseModel):
    """读取租客档案"""
    model_config = {"from_attributes": True}
    id: int
    user_id: int
    is_default: bool = False
    label: str | None = None
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
    enrollment_level: str | None = None
    enrollment_term: str | None = None
    student_classification: str | None = None
    preferred_name: str | None = None
    is_international: bool = True
    visa_type: str | None = None
    visa_expiry: date | None = None
    citizenship_country: str | None = None
    disability_needs: str | None = None
    dietary_needs: str | None = None
    gender_identity: str | None = None
    created_at: datetime
    updated_at: datetime


class TenantListResponse(BaseModel):
    items: list[TenantRead]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── 订单（保留，未改动）──

class OrderCreate(BaseModel):
    room_id: int
    tenant_id: int
    start_date: date
    end_date: date
    total_amount: Decimal = Field(..., ge=0)
    deposit_status: str = "unpaid"
    status: str = "active"


class OrderUpdate(BaseModel):
    room_id: int | None = None
    tenant_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    total_amount: Decimal | None = Field(default=None, ge=0)
    deposit_status: str | None = None
    status: str | None = None


class OrderRead(BaseModel):
    id: int
    room_id: int | None = None
    tenant_id: int | None = None
    tenant_name: str | None = None
    start_date: date
    end_date: date
    total_amount: Decimal
    deposit_status: str = "unpaid"
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderRead]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── 流转记录 ──

class RoomTransferRead(BaseModel):
    id: int
    room_id: int
    from_status: str | None = None
    to_status: str
    reason: str | None = None
    operator_id: int | None = None
    created_at: datetime
    model_config = {"from_attributes": True}

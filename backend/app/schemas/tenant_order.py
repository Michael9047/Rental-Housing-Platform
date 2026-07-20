"""房客 & 订单 Pydantic 模式"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ── 房客 ──
class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = None
    email: str | None = None
    id_number: str | None = None
    emergency_contact: str | None = None


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = None
    email: str | None = None
    id_number: str | None = None
    emergency_contact: str | None = None


class TenantRead(BaseModel):
    id: int
    name: str
    phone: str | None = None
    email: str | None = None
    id_number: str | None = None
    emergency_contact: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── 订单 ──
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


# ── 列表响应 ──
class TenantListResponse(BaseModel):
    items: list[TenantRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderListResponse(BaseModel):
    items: list[OrderRead]
    total: int
    page: int
    page_size: int
    total_pages: int

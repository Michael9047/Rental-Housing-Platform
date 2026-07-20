"""房间 Pydantic 模式"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    """创建房间"""
    unit_type_id: int = Field(..., description="所属户型ID")
    landlord_id: int = Field(..., description="房东ID")
    room_number: str | None = Field(default=None, description="房号")
    floor: int | None = Field(default=None, description="楼层(选填)")
    special_discount: Decimal | None = Field(default=None, ge=0, description="专属优惠")
    available_from: date | None = Field(default=None)
    min_stay_months: int = Field(default=3, ge=1)
    status: str = Field(default="available")


class RoomUpdate(BaseModel):
    """更新房间"""
    room_number: str | None = None
    floor: int | None = None
    special_discount: Decimal | None = Field(default=None, ge=0)
    available_from: date | None = None
    min_stay_months: int | None = Field(default=None, ge=1)
    status: str | None = None
    version: int | None = Field(default=None, ge=1, description="乐观锁版本号")


class RoomImageRead(BaseModel):
    id: int
    room_id: int
    filename: str
    original_name: str
    mime_type: str
    file_size: int
    sort_order: int
    is_primary: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class RoomRead(BaseModel):
    """房间响应 — 含继承的户型/公寓信息"""
    id: int
    landlord_id: int
    unit_type_id: int
    room_number: str | None = None
    floor: int | None = None
    special_discount: Decimal | None = None
    available_from: date | None = None
    min_stay_months: int
    status: str
    version: int
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # 继承信息（从户型/公寓链获取）
    unit_type_name: str | None = None
    base_rent: Decimal | None = None
    area_sqm: Decimal | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    hall_count: int | None = None
    deposit_amount: int | None = None
    amenities: list[str] | None = None
    institute_id: int | None = None
    institute_name: str | None = None
    institute_address: str | None = None

    images: list[RoomImageRead] = []
    primary_image_url: str | None = None

    model_config = {"from_attributes": True}


class RoomListResponse(BaseModel):
    items: list[RoomRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class BatchStatusUpdate(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)
    status: str = Field(..., description="目标状态")


class BatchDelete(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)

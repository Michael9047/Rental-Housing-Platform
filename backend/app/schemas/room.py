<<<<<<< HEAD
"""房间 Pydantic 模式（稳定版）"""
=======
"""已废弃 — Room 表已删除。保留兼容导入。"""
>>>>>>> merge/pr33-pr35
from datetime import date, datetime
from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
<<<<<<< HEAD
    unit_type_id: int = Field(..., description="所属户型ID")
    landlord_id: int = Field(..., description="房东ID")
    room_number: str | None = None
    building_block: str | None = None
    floor: int | None = None
    special_discount: str | None = None
    available_from: date | None = None
    min_stay_months: int = Field(default=3, ge=1)
    status: str = Field(default="available")


class RoomUpdate(BaseModel):
    room_number: str | None = None
    building_block: str | None = None
    floor: int | None = None
    special_discount: str | None = None
    available_from: date | None = None
    min_stay_months: int | None = Field(default=None, ge=1)
    status: str | None = None
    version: int | None = Field(default=None, ge=1)


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
    id: int
    landlord_id: int
=======
    pass


class RoomUpdate(BaseModel):
    pass


class RoomRead(BaseModel):
    id: int = 0
    landlord_id: int = 0
>>>>>>> merge/pr33-pr35
    business_id: str | None = None
    uuid: str | None = None
    unit_type_id: int | None = None
    room_number: str | None = None
    building_block: str | None = None
    floor: int | None = None
    special_discount: str | None = None
    available_from: date | None = None
    min_stay_months: int | None = None
<<<<<<< HEAD
    status: str
    version: int
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # 继承自户型/公寓
    unit_type_name: str | None = None
    base_rent: float | None = None
    area_sqm: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    hall_count: int | None = None
    deposit_amount: float | None = None
    amenities: list[str] | None = None
    institute_name: str | None = None
    institute_address: str | None = None

    images: list[RoomImageRead] = []
=======
    status: str = ""
    version: int = 0
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    images: list = []
>>>>>>> merge/pr33-pr35
    primary_image_url: str | None = None


class RoomListResponse(BaseModel):
    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class BatchStatusUpdate(BaseModel):
<<<<<<< HEAD
    ids: list[int] = Field(..., min_length=1, max_length=500)
    status: str
=======
    ids: list[int] = []
    status: str = ""
>>>>>>> merge/pr33-pr35


class BatchDelete(BaseModel):
    ids: list[int] = []

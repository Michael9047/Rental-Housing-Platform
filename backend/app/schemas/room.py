"""已废弃 — Room 表已删除。保留兼容导入。"""
from datetime import date, datetime
from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    pass


class RoomUpdate(BaseModel):
    pass


class RoomRead(BaseModel):
    id: int = 0
    landlord_id: int = 0
    business_id: str | None = None
    uuid: str | None = None
    unit_type_id: int | None = None
    room_number: str | None = None
    building_block: str | None = None
    floor: int | None = None
    special_discount: str | None = None
    available_from: date | None = None
    min_stay_months: int | None = None
    status: str = ""
    version: int = 0
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    images: list = []
    primary_image_url: str | None = None


class RoomListResponse(BaseModel):
    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class BatchStatusUpdate(BaseModel):
    ids: list[int] = []
    status: str = ""


class BatchDelete(BaseModel):
    ids: list[int] = []

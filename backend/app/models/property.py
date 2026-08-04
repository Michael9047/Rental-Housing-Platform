"""兼容桥接 — Room 表已删除，重定向到 UnitType / Institute / BuildingImage。"""
from app.models.unit_type import (
    UnitType as Property,
    UnitType as Room,
    UnitTypeStatus as PropertyStatus,
    UnitTypeStatus as RoomStatus,
    PropertyType,
    DepositType,
)
from app.models.building_image import BuildingImage as PropertyImage, BuildingImage as RoomImage

# 状态流转表已废弃，保留空字典兼容旧引用
VALID_ROOM_STATUS_TRANSITIONS: dict = {}
VALID_STATUS_TRANSITIONS: dict = {}

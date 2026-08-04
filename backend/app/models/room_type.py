"""兼容桥接 — RoomType 表已删除，已被 UnitType 替代。"""
from app.models.unit_type import (
    UnitType as RoomType,
    UnitTypeStatus as RoomTypeStatus,
    RoomTypeEnum,
    DepositType,
)

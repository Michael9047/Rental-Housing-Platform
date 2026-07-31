"""已废弃 — Room 表已删除。保留兼容导入，业务逻辑请迁移到 UnitType。"""
from app.models._compat import (
    DepositType,
    Property,
    PropertyImage,
    PropertyStatus,
    PropertyType,
    Room,
    RoomImage,
    RoomStatus,
    VALID_ROOM_STATUS_TRANSITIONS,
    VALID_STATUS_TRANSITIONS,
)

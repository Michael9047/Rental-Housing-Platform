<<<<<<< HEAD
"""房间模型 — 三层架构最底层出租单元（瘦身后：仅存房间独有字段）"""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class RoomStatus(str, enum.Enum):
    available = "available"
    pending_review = "pending_review"
    rented = "rented"
    maintenance = "maintenance"
    offline = "offline"


VALID_ROOM_STATUS_TRANSITIONS: dict[RoomStatus, set[RoomStatus]] = {
    RoomStatus.available: {RoomStatus.offline, RoomStatus.rented, RoomStatus.maintenance},
    RoomStatus.pending_review: {RoomStatus.available, RoomStatus.offline},
    RoomStatus.rented: {RoomStatus.maintenance, RoomStatus.offline},
    RoomStatus.maintenance: {RoomStatus.available, RoomStatus.offline},
    RoomStatus.offline: {RoomStatus.available, RoomStatus.pending_review},
}


class Room(TimestampMixin, Base):
    """房间 — 最底层出租单元，绑定户型。价格/面积/户型等从 unit_type JOIN 获取。"""
    __tablename__ = "rooms"

    # ── 标识 ──
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    business_id: Mapped[str | None] = mapped_column(String(24), unique=True, index=True, nullable=True)
    uuid: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)

    # ── 归属 ──
    landlord_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    unit_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit_types.id", ondelete="SET NULL"), index=True, nullable=True
    )
    institute_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # ── 房间独有信息 ──
    room_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    building_block: Mapped[str | None] = mapped_column(String(20), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    special_discount: Mapped[str | None] = mapped_column(String(200), nullable=True)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── 安全评分（房间级）──
    safety_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    # ── 房间细节（StarRez 对照）──
    gender_allocation: Mapped[str | None] = mapped_column(String(20), nullable=True)  # male / female / coed / dynamic
    bed_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # single / twin / double / bunk
    max_occupancy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathroom_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ensuite / shared / private
    furnished: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    utilities_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    internet_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    floor_plan_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── 状态与版本 ──
    status: Mapped[str] = mapped_column(
        Enum(RoomStatus, name="property_status", create_type=False),
        default="available", nullable=False, index=True
    )
    min_stay_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_lease_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_lease_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # ── 关系 ──
    landlord: Mapped["User"] = relationship(back_populates="rooms")
    unit_type: Mapped["UnitType"] = relationship(
        "UnitType", back_populates="rooms",
        foreign_keys="[Room.unit_type_id]",
    )
    images: Mapped[list["RoomImage"]] = relationship(
        "RoomImage", back_populates="room", cascade="all, delete-orphan", lazy="selectin"
    )


# 向后兼容别名
Property = Room
PropertyStatus = RoomStatus
VALID_STATUS_TRANSITIONS = VALID_ROOM_STATUS_TRANSITIONS

# 旧枚举别名
import enum as _enum2
class PropertyType(str, _enum2.Enum):
    studio = "studio"      # 单间/开间
    one_bed = "1-bed"      # 一室一厅公寓
    two_bed = "2-bed"      # 两室及以上公寓
    shared = "shared"      # 合租单间
    house = "house"        # 独栋/联排别墅
# DepositType 从 unit_type 导入
from app.models.unit_type import DepositType as _DT
DepositType = _DT
=======
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
>>>>>>> merge/pr33-pr35

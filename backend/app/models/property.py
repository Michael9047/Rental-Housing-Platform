"""房间模型 — 三层架构最底层出租单元（稳定版）"""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
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
    """房间 — 最底层出租单元，绑定户型"""
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

    # ── 房间特有信息 ──
    room_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    building_block: Mapped[str | None] = mapped_column(String(20), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    special_discount: Mapped[str | None] = mapped_column(String(200), nullable=True)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── 状态 ──
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="room_status", create_constraint=True),
        default=RoomStatus.available, nullable=False, index=True,
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
    apartment = "apartment"
    house = "house"
    studio = "studio"
    shared = "shared"

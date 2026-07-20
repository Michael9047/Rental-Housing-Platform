"""房间模型 — 三层架构最底层出租单元"""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class RoomStatus(str, enum.Enum):
    available = "available"          # 可租
    pending_review = "pending_review"  # 待审核
    rented = "rented"               # 已出租
    maintenance = "maintenance"      # 维护中
    offline = "offline"             # 已下线


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

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    landlord_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # ── 户型绑定 ──
    unit_type_id: Mapped[int] = mapped_column(ForeignKey("unit_types.id", ondelete="CASCADE"), index=True)

    # ── 房间独有信息 ──
    room_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    institute_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # 兼容旧代码的字段
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price_monthly: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deposit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_fee_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 三层架构真正字段
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    special_discount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── 状态与版本 ──
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="property_status"),
        default=RoomStatus.available,
        nullable=False,
        index=True,
    )
    min_stay_months: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # ── 关系 ──
    landlord: Mapped["User"] = relationship(back_populates="rooms")
    unit_type: Mapped["UnitType"] = relationship(back_populates="rooms")
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
# DepositType 从 unit_type 导入
from app.models.unit_type import DepositType as _DT
DepositType = _DT

"""户型模型 — 三层架构中间核心录入主体"""
import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class UnitTypeStatus(str, enum.Enum):
    available = "available"
    rented = "rented"
    maintenance = "maintenance"


class DepositType(str, enum.Enum):
    one_month = "one_month"
    one_three = "one_three"
    two_month = "two_month"
    three_month = "three_month"
    half_month = "half_month"
    free = "free"
    custom = "custom"


class UnitType(TimestampMixin, Base):
    """户型 — 中间层核心录入主体，归属于公寓 (institute)"""
    __tablename__ = "unit_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    hall_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    base_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    deposit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_type: Mapped[DepositType | None] = mapped_column(
        Enum(DepositType, name="room_type_deposit_type"), nullable=True
    )
    lease_start: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lease_end: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), default="CNY")
    special_offer: Mapped[str | None] = mapped_column(Text, nullable=True)

    floor_pricing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    amenities: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    min_stay_months: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    status: Mapped[UnitTypeStatus] = mapped_column(
        Enum(UnitTypeStatus, name="room_type_status"),
        default=UnitTypeStatus.available, nullable=False
    )

    # ── 关系 ──
    institute: Mapped["Institute"] = relationship(back_populates="unit_types")
    rooms: Mapped[list["Room"]] = relationship(
        "Room", back_populates="unit_type", cascade="all, delete-orphan", lazy="selectin",
        foreign_keys="[Room.unit_type_id]",
    )


# 向后兼容别名
RoomType = UnitType
RoomTypeStatus = UnitTypeStatus

import enum as _enum
class RoomTypeEnum(str, _enum.Enum):
    studio = "studio"
    ensuite = "ensuite"
    _1bed = "1bed"
    _2bed = "2bed"
    _3bed_plus = "3bed+"
    shared = "shared"

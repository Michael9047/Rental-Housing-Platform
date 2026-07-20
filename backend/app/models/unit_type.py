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
    one_month = "one_month"       # 押一付一
    one_three = "one_three"       # 押一付三
    two_month = "two_month"       # 押二付一
    three_month = "three_month"   # 押三付一
    half_month = "half_month"     # 押半付一
    free = "free"                 # 免押金
    custom = "custom"             # 自定义


class UnitType(TimestampMixin, Base):
    """户型 — 中间层核心录入主体，归属于公寓"""
    __tablename__ = "unit_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── 所属公寓 ──
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # ── 基本信息 ──
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    hall_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── 面积与租金 ──
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    base_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_type: Mapped[DepositType | None] = mapped_column(
        Enum(DepositType, name="room_type_deposit_type"), nullable=True, default=None
    )

    # ── 楼层差异化加价 ──
    # [{"floor_min": 1, "floor_max": 5, "adjustment": 0}, {"floor_min": 6, "floor_max": 10, "adjustment": 200}]
    floor_pricing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── 配置 ──
    amenities: Mapped[list[str] | None] = mapped_column(ARRAY(String(30)), nullable=True)
    image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    min_stay_months: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # ── 状态 ──
    status: Mapped[UnitTypeStatus] = mapped_column(
        Enum(UnitTypeStatus, name="room_type_status"),
        default=UnitTypeStatus.available,
        nullable=False,
    )

    # ── 关系 ──
    institute: Mapped["Institute"] = relationship(back_populates="unit_types")
    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="unit_type", cascade="all, delete-orphan", lazy="selectin")

# 向后兼容别名
import enum as _enum
RoomType = UnitType
RoomTypeStatus = UnitTypeStatus
class RoomTypeEnum(str, _enum.Enum):
    studio = "studio"
    ensuite = "ensuite"
    _1bed = "1bed"
    _2bed = "2bed"
    _3bed_plus = "3bed+"
    shared = "shared"

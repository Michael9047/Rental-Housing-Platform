"""户型模型 — 三层架构中间核心录入主体（稳定版）"""
import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
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
    """户型 — 中间层核心录入主体，归属于公寓"""
    __tablename__ = "unit_types"

    # ── 标识 ──
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    business_id: Mapped[str | None] = mapped_column(String(24), unique=True, index=True, nullable=True)
    uuid: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)

    # ── 所属公寓 ──
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # ── 基本信息 ──
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hall_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── 面积 ──
    area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── 租金（float — 前端直接输入，无需 Decimal 精度）──
    base_rent: Mapped[float] = mapped_column(Float, nullable=False)
    deposit_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    deposit_type: Mapped[DepositType | None] = mapped_column(
        Enum(DepositType, name="unit_type_deposit_type"), nullable=True, default=None
    )
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="CNY")

    # ── 租期 — 自由文本(AI可读) + 结构化Date(DB可查) ──
    lease_start: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lease_end: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lease_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lease_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── 优惠 ──
    special_offer: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 楼层差异化加价 ──
    floor_pricing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── 配置 ──
    amenities: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    min_stay_months: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 状态 ──
    status: Mapped[UnitTypeStatus] = mapped_column(
        Enum(UnitTypeStatus, name="unit_type_status", create_constraint=True),
        default=UnitTypeStatus.available, nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # ── 关系 ──
    institute: Mapped["Institute"] = relationship(back_populates="unit_types")
    images: Mapped[list["UnitTypeImage"]] = relationship(
        "UnitTypeImage", back_populates="unit_type",
        cascade="all, delete-orphan", lazy="selectin",
    )
    rooms: Mapped[list["Room"]] = relationship(
        "Room", back_populates="unit_type",
        cascade="all, delete-orphan", lazy="selectin",
    )


class UnitTypeImage(TimestampMixin, Base):
    """户型图片 — 独立子表，统一与公寓 BuildingImage 一致的设计"""
    __tablename__ = "unit_type_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    unit_type_id: Mapped[int] = mapped_column(
        ForeignKey("unit_types.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)

    unit_type: Mapped["UnitType"] = relationship(back_populates="images")


# 向后兼容
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

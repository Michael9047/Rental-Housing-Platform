"""房型模型 — 一个 Property（楼栋）下可有多个 RoomType（如 Studio/Ensuite/1Bed/2Bed），各自独立定价。"""
import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Text as SAText
from app.models.types import string_array
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class RoomTypeEnum(str, enum.Enum):
    """房型分类"""
    studio = "studio"               # Studio 单人间
    ensuite = "ensuite"             # Ensuite 独卫套间
    one_bed = "1bed"                # 一室一厅
    two_bed = "2bed"                # 两室一厅
    three_bed_plus = "3bed+"        # 三室及以上
    shared = "shared"               # 共享/合租


class RoomTypeStatus(str, enum.Enum):
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


class RoomType(TimestampMixin, Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # 房型基本信息
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[RoomTypeEnum] = mapped_column(
        Enum(RoomTypeEnum, name="room_type_enum"),
        default=RoomTypeEnum.studio,
        nullable=False,
    )
    bedrooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 可租信息
    available_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    min_stay_months: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # 押金
    deposit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_type: Mapped[DepositType | None] = mapped_column(
        Enum(DepositType, name="room_type_deposit_type"), nullable=True, default=None
    )

    # 设施与描述
    amenities: Mapped[list[str] | None] = mapped_column(string_array(30), nullable=True)
    description: Mapped[str | None] = mapped_column(SAText, nullable=True)

    # 状态
    status: Mapped[RoomTypeStatus] = mapped_column(
        Enum(RoomTypeStatus, name="room_type_status"),
        default=RoomTypeStatus.available,
        nullable=False,
    )

    # 关系
    property: Mapped["Property"] = relationship(back_populates="room_types")

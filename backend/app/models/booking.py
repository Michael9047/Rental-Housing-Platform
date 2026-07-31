"""预约模型 — 核心订单枢纽"""
import enum
from datetime import datetime, date

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text as SAText
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class BookingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"
    contract_ready = "contract_ready"
    contract_signed = "contract_signed"
    payment_pending = "payment_pending"
    payment_processing = "payment_processing"
    paid = "paid"
    payment_failed = "payment_failed"
    payment_expired = "payment_expired"
    refund_pending = "refund_pending"
    refunded = "refunded"
    payment_review = "payment_review"


class Booking(TimestampMixin, Base):
    """预约订单 — 三层关联：user(谁操作) + tenant(用谁的信息) + unit_type(订什么)"""
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── 关联 ──
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), index=True, nullable=True
    )
<<<<<<< HEAD
    property_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
=======
    unit_type_id: Mapped[int] = mapped_column(
        ForeignKey("unit_types.id", ondelete="SET NULL"), index=True, nullable=True
>>>>>>> merge/pr33-pr35
    )
    institute_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutes.id", ondelete="SET NULL"), index=True, nullable=True
    )
    bm_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    room_number: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="BM填的房号")

    # ── 日期 ──
    scheduled_date: Mapped[str | None] = mapped_column(String(32), comment="预计入住日")
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True, comment="合同开始日")
    contract_end:   Mapped[date | None] = mapped_column(Date, nullable=True, comment="合同结束日")
    lease_months:   Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── 金额 ──
    deposit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_fee:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_rent:     Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── 状态 ──
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.pending,
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(SAText)

    # ── 支付 ──
    deposit_status: Mapped[str] = mapped_column(String(20), default="unpaid")
    payment_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inventory_reserved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

<<<<<<< HEAD
    tenant: Mapped["User"] = relationship(foreign_keys=[tenant_id])
    property: Mapped["Room"] = relationship()
    landlord: Mapped["User"] = relationship(foreign_keys=[landlord_id])
=======
    # ── 快照 ──
    application_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="{pricing_snapshot}")

    # ── 关系 ──
    user:      Mapped["User"] = relationship(foreign_keys=[user_id])
    tenant:    Mapped["Tenant | None"] = relationship(foreign_keys=[tenant_id])
    unit_type: Mapped["UnitType | None"] = relationship(foreign_keys=[unit_type_id])
    institute: Mapped["Institute | None"] = relationship(foreign_keys=[institute_id])
    bm:        Mapped["User | None"] = relationship(foreign_keys=[bm_id])
>>>>>>> merge/pr33-pr35

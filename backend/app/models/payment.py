import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"
    closed = "closed"
    refunded = "refunded"


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    out_trade_no: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    prepay_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=PaymentStatus.pending.value, nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        String(50), default="wechat_pay"
    )
    trade_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trade_state_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    booking: Mapped["Booking"] = relationship()
    user: Mapped["User"] = relationship()

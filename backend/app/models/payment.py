import enum
import uuid
from datetime import datetime

from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"
    closed = "closed"
    expired = "expired"
    review = "review"
    refund_pending = "refund_pending"
    refunded = "refunded"


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    payment_attempt_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    out_trade_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trade_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trade_state_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.pending,
        nullable=False,
    )
    payment_method: Mapped[str] = mapped_column(
        String(50), default="wechat_pay"
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settlement_currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    settlement_amount_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cny_reference_amount_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    property_currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(24, 12), default=Decimal("1"), nullable=False)
    exchange_rate_source: Mapped[str] = mapped_column(String(200), default="platform snapshot", nullable=False)
    exchange_rate_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="mock_hosted", nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    provider_checkout_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    provider_merchant_account: Mapped[str | None] = mapped_column(String(100))
    checkout_url: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    booking: Mapped["Booking"] = relationship()
    user: Mapped["User"] = relationship()

    @property
    def order_status(self) -> str | None:
        """向支付页面暴露明确的后端订单状态。"""
        booking = self.__dict__.get("booking")
        if booking is None:
            return None
        return booking.status.value if hasattr(booking.status, "value") else str(booking.status)


class PaymentWebhookEvent(Base):
    """保存支付服务商事件编号，保证 webhook 重复投递幂等。"""

    __tablename__ = "payment_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_payment_webhook_provider_event"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

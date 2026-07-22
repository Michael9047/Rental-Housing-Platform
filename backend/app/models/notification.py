import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text as SAText, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class NotificationType(str, enum.Enum):
    booking_created = "booking_created"
    booking_approved = "booking_approved"
    booking_rejected = "booking_rejected"
    booking_cancelled = "booking_cancelled"
    booking_completed = "booking_completed"
    payment_received = "payment_received"
    payment_created = "payment_created"
    payment_failed = "payment_failed"
    payment_expired = "payment_expired"
    contract_generated = "contract_generated"
    contract_signed = "contract_signed"
    auth_registration = "auth_registration"
    auth_password_reset = "auth_password_reset"
    repair_created = "repair_created"
    repair_assigned = "repair_assigned"
    repair_completed = "repair_completed"
    repair_status_change = "repair_status_change"
    system = "system"


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(SAText)
    # 结构化关联字段；content 保留用于兼容历史通知正文。
    body: Mapped[str | None] = mapped_column(SAText)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    order_id: Mapped[str | None] = mapped_column(String(64))
    agreement_id: Mapped[str | None] = mapped_column(String(100))
    property_id: Mapped[int | None] = mapped_column(Integer)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
        Index("ix_notifications_user_entity", "user_id", "entity_type", "entity_id"),
    )


class NotificationOutboxStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    sent = "sent"
    failed = "failed"


class NotificationOutbox(TimestampMixin, Base):
    """与业务状态同事务写入的可靠通知发件箱。"""
    __tablename__ = "notification_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_key: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    template_version: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[NotificationOutboxStatus] = mapped_column(Enum(NotificationOutboxStatus, name="notification_outbox_status"), default=NotificationOutboxStatus.pending, nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))

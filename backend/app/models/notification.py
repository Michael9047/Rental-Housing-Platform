import enum

from sqlalchemy import Enum, ForeignKey, String, Text as SAText
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
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship()

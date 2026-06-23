import enum

from sqlalchemy import Enum, ForeignKey, String, Text as SAText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class BookingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    landlord_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.pending,
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(SAText)
    scheduled_date: Mapped[str | None] = mapped_column(String(32))

    tenant: Mapped["User"] = relationship(foreign_keys=[tenant_id])
    property: Mapped["Property"] = relationship()
    landlord: Mapped["User"] = relationship(foreign_keys=[landlord_id])

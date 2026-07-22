import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text as SAText
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.mixins import TimestampMixin
from app.db.session import Base


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    template_name: Mapped[str] = mapped_column(String(100), default="standard_lease")
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    booking: Mapped["Booking"] = relationship()
    tenant: Mapped["User"] = relationship(foreign_keys=[tenant_id])
    property: Mapped["Room"] = relationship()
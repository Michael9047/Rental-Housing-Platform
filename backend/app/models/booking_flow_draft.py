"""预订流程草稿模型。"""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import TimestampMixin
from app.db.session import Base


class BookingFlowDraft(TimestampMixin, Base):
    __tablename__ = "booking_flow_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True)
    current_step: Mapped[str] = mapped_column(String(32), default="move_in_date")
    move_in_date: Mapped[str | None] = mapped_column(String(32))
    lease_months: Mapped[int | None] = mapped_column(Integer)
    personal_info: Mapped[dict | None] = mapped_column(JSONB)
    emergency_contact: Mapped[dict | None] = mapped_column(JSONB)

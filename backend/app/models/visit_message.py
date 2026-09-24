"""预约看房消息模型"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base


class VisitMessage(Base):
    __tablename__ = "apartment_visit_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("institutes.id", ondelete="CASCADE"), index=True, nullable=False)
    guest_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    guest_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

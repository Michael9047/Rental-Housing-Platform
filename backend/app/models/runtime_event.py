from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RuntimeEvent(Base):
    __tablename__ = "runtime_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str | None] = mapped_column(String(12))
    path: Mapped[str | None] = mapped_column(String(240), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, index=True)
    request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    extra: Mapped[dict | None] = mapped_column(JSON)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

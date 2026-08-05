import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin


class SystemAlertSeverity(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class SystemAlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class SystemAlert(TimestampMixin, Base):
    __tablename__ = "system_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[SystemAlertSeverity] = mapped_column(
        Enum(SystemAlertSeverity, name="system_alert_severity"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[SystemAlertStatus] = mapped_column(
        Enum(SystemAlertStatus, name="system_alert_status"),
        default=SystemAlertStatus.open,
        nullable=False,
        index=True,
    )
    action_type: Mapped[str | None] = mapped_column(String(60))
    action_label: Mapped[str | None] = mapped_column(String(60))
    action_resource_id: Mapped[str | None] = mapped_column(String(120))
    extra: Mapped[dict | None] = mapped_column(JSON)
    reported_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resolved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def mark_resolved(self, user_id: int | None = None) -> None:
        self.status = SystemAlertStatus.resolved
        self.resolved_by_id = user_id
        self.resolved_at = datetime.now(timezone.utc)


class SystemAlertProcessRecord(Base):
    __tablename__ = "system_alert_process_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    alert_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    system_alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("system_alerts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), index=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    status_before: Mapped[str | None] = mapped_column(String(80))
    status_after: Mapped[str | None] = mapped_column(String(80))
    handled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    extra: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

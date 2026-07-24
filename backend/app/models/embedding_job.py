import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text as SAText
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EmbeddingJobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class EmbeddingJob(Base):
    __tablename__ = "embedding_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[EmbeddingJobStatus] = mapped_column(
        Enum(EmbeddingJobStatus, name="embedding_job_status"),
        default=EmbeddingJobStatus.pending,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(SAText)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

"""记录公寓级联进入回收站时实际影响的户型及其原状态。"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ListingDeletionBatch(Base):
    __tablename__ = "listing_deletion_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    building_status: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_types: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

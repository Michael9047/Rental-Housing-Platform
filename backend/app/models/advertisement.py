"""广告系统模型（v2）。"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text as SAText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class AdvertisementStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    ended = "ended"
    rejected = "rejected"


class Advertisement(TimestampMixin, Base):
    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    target_url: Mapped[str | None] = mapped_column(String(500))
    district: Mapped[str | None] = mapped_column(String(100), index=True)
    placement: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    budget: Mapped[float | None] = mapped_column(Float)
    cost_per_click: Mapped[float | None] = mapped_column(Float)
    start_date: Mapped[str] = mapped_column(String(32), nullable=False)
    end_date: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[AdvertisementStatus] = mapped_column(
        Enum(AdvertisementStatus, name="advertisement_status"),
        default=AdvertisementStatus.draft,
        nullable=False,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    creator: Mapped["User"] = relationship()


class AdImpression(Base):
    __tablename__ = "ad_impressions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ad_id: Mapped[int] = mapped_column(
        ForeignKey("advertisements.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    ad: Mapped["Advertisement"] = relationship()

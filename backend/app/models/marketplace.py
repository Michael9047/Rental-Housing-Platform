"""二手交易市场模块 - 类闲鱼功能（v2）。"""
import enum

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text as SAText
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class MarketplaceItemStatus(str, enum.Enum):
    active = "active"
    sold = "sold"
    removed = "removed"


class MarketplaceItemCondition(str, enum.Enum):
    new = "new"
    like_new = "like_new"
    good = "good"
    fair = "fair"


class MarketplaceReportStatus(str, enum.Enum):
    pending = "pending"
    resolved = "resolved"
    dismissed = "dismissed"


# --- 二手商品 ---
class MarketplaceItem(TimestampMixin, Base):
    __tablename__ = "marketplace_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(SAText)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    condition: Mapped[MarketplaceItemCondition] = mapped_column(
        Enum(MarketplaceItemCondition, name="marketplace_item_condition"),
        default=MarketplaceItemCondition.good,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    district: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[MarketplaceItemStatus] = mapped_column(
        Enum(MarketplaceItemStatus, name="marketplace_item_status"),
        default=MarketplaceItemStatus.active,
        nullable=False,
        index=True,
    )
    moderation_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    seller: Mapped["User"] = relationship(foreign_keys=[seller_id])
    images: Mapped[list["MarketplaceItemImage"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", lazy="selectin"
    )
    comments: Mapped[list["MarketplaceComment"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", lazy="selectin"
    )


# --- 商品图片 ---
class MarketplaceItemImage(Base):
    __tablename__ = "marketplace_item_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    item: Mapped["MarketplaceItem"] = relationship(back_populates="images")


# --- 用户间私聊消息 ---
class MarketplaceMessage(TimestampMixin, Base):
    __tablename__ = "marketplace_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    moderation_status: Mapped[str] = mapped_column(
        String(20), default="approved", nullable=False
    )

    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    receiver: Mapped["User"] = relationship(foreign_keys=[receiver_id])
    item: Mapped["MarketplaceItem"] = relationship()


# --- 商品公开评论 ---
class MarketplaceComment(TimestampMixin, Base):
    __tablename__ = "marketplace_comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    moderation_status: Mapped[str] = mapped_column(
        String(20), default="approved", nullable=False
    )

    item: Mapped["MarketplaceItem"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship()


# --- 举报记录 ---
class MarketplaceReport(TimestampMixin, Base):
    __tablename__ = "marketplace_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[MarketplaceReportStatus] = mapped_column(
        Enum(MarketplaceReportStatus, name="marketplace_report_status"),
        default=MarketplaceReportStatus.pending,
        nullable=False,
        index=True,
    )
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolution_note: Mapped[str | None] = mapped_column(SAText)

    reporter: Mapped["User"] = relationship(foreign_keys=[reporter_id])
    resolver: Mapped["User | None"] = relationship(foreign_keys=[resolved_by])
    item: Mapped["MarketplaceItem"] = relationship()

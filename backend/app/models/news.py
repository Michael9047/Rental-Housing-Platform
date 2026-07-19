"""本地新闻资讯模型（v2）。"""
import enum

from sqlalchemy import DateTime, Enum, String, Text as SAText
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import TimestampMixin
from app.db.session import Base


class NewsArticleStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class NewsArticle(TimestampMixin, Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    district: Mapped[str | None] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True, default="general")
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[NewsArticleStatus] = mapped_column(
        Enum(NewsArticleStatus, name="news_article_status"),
        default=NewsArticleStatus.draft,
        nullable=False,
    )
    published_at: Mapped[str | None] = mapped_column(String(32))

"""对话模型 —— 区分普通客服聊天与租房 Agent 会话。"""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text as SAText
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class ChatSessionStatus(str, enum.Enum):
    active = "active"
    closed = "closed"


class ChatMessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=lambda: uuid.uuid4().hex
    )
    title: Mapped[str | None] = mapped_column(String(200))
    # 线上旧库使用 ``kind``；Python 侧继续保留 session_kind 名称，
    # 这样无需迁移也能区分普通聊天与租房 Agent 会话。
    session_kind: Mapped[str] = mapped_column(
        "kind", String(32), default="chat", server_default="chat", nullable=False, index=True
    )
    status: Mapped[ChatSessionStatus] = mapped_column(
        Enum(ChatSessionStatus, name="chat_session_status"),
        default=ChatSessionStatus.active,
        nullable=False,
    )
    accumulated_filters: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatMessageRole] = mapped_column(
        Enum(ChatMessageRole, name="chat_message_role"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

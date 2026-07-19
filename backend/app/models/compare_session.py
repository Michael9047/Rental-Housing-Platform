"""对比 Agent 会话模型 —— 深度对比的持久化状态"""
import enum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text as SAText
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class CompareSessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"


class CompareMessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"


class CompareSession(TimestampMixin, Base):
    """对比会话 —— 一次对比（可能包含多轮追问）"""

    __tablename__ = "compare_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    property_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="balanced")
    status: Mapped[CompareSessionStatus] = mapped_column(
        Enum(CompareSessionStatus, name="compare_session_status"),
        default=CompareSessionStatus.active,
        nullable=False,
    )
    # 缓存最近一次对比结果，快速回溯无需重新计算
    result_cache: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    messages: Mapped[list["CompareMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class CompareMessage(TimestampMixin, Base):
    """对比会话中的一条消息（用户提问 / Agent 回复 / 工具调用）"""

    __tablename__ = "compare_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("compare_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(SAText, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    session: Mapped["CompareSession"] = relationship(back_populates="messages")

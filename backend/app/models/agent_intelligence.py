"""Agent 智能层模型 —— 会话状态、长期记忆与检索可观测记录。"""
from __future__ import annotations

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


# PostgreSQL 使用 JSONB；测试环境 SQLite 自动退回通用 JSON。
JSON_DOCUMENT = JSON().with_variant(JSONB, "postgresql")


class AgentSessionState(TimestampMixin, Base):
    """单个 Agent 会话的短期记忆与指代映射。"""

    __tablename__ = "agent_session_states"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_agent_session_states_session_id"),
        Index("ix_agent_session_states_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="explore")
    filters_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    reference_map_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    last_search_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    rolling_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AgentUserMemory(TimestampMixin, Base):
    """跨会话长期记忆；每个用户一行，字段内保留置信度与证据次数。"""

    __tablename__ = "agent_user_memories"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_agent_user_memories_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    preferences_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    profile_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentSearchRun(TimestampMixin, Base):
    """一次搜索的查询理解、放宽轨迹和来源清单。"""

    __tablename__ = "agent_search_runs"
    __table_args__ = (
        Index("ix_agent_search_runs_session_created", "session_id", "created_at"),
        Index("ix_agent_search_runs_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_query: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_filters_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    relaxation_trace_json: Mapped[list] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    source_manifest_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    candidates: Mapped[list["AgentSearchCandidate"]] = relationship(
        back_populates="search_run", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentSearchCandidate(TimestampMixin, Base):
    """检索候选的最终名次、总分与可解释分项。"""

    __tablename__ = "agent_search_candidates"
    __table_args__ = (
        UniqueConstraint(
            "search_run_id", "unit_type_id", name="uq_agent_search_candidate_run_unit"
        ),
        UniqueConstraint(
            "search_run_id", "rank", name="uq_agent_search_candidate_run_rank"
        ),
        Index("ix_agent_search_candidates_run_rank", "search_run_id", "rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_search_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit_types.id", ondelete="SET NULL"), nullable=True, index=True
    )
    property_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit_types.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    source_metadata_json: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)

    search_run: Mapped[AgentSearchRun] = relationship(back_populates="candidates")

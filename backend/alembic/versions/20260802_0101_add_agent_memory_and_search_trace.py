"""新增 Agent 会话记忆、长期记忆与检索追踪表

Revision ID: 20260802_0101
Revises: 20260725_0100
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260802_0101"
down_revision: Union[str, Sequence[str], None] = "20260725_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column(
            "session_kind",
            sa.String(length=32),
            server_default="chat",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chat_sessions_session_kind",
        "chat_sessions",
        ["session_kind"],
    )
    # 旧 Agent 会话创建时使用固定标题；迁移时尽量保留已有记录。
    op.execute(
        "UPDATE chat_sessions SET session_kind = 'agent' "
        "WHERE title = '租房推荐 Agent'"
    )

    op.create_table(
        "agent_session_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("filters_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reference_map_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_search_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rolling_summary", sa.Text(), nullable=True),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_agent_session_states_session_id"),
    )
    op.create_index("ix_agent_session_states_session_id", "agent_session_states", ["session_id"])
    op.create_index("ix_agent_session_states_user_id", "agent_session_states", ["user_id"])
    op.create_index(
        "ix_agent_session_states_user_updated",
        "agent_session_states",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "agent_user_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("preferences_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("profile_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_agent_user_memories_user_id"),
    )
    op.create_index("ix_agent_user_memories_user_id", "agent_user_memories", ["user_id"])

    op.create_table(
        "agent_search_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=False),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("effective_filters_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("relaxation_trace_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_manifest_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_search_runs_session_id", "agent_search_runs", ["session_id"])
    op.create_index("ix_agent_search_runs_user_id", "agent_search_runs", ["user_id"])
    op.create_index(
        "ix_agent_search_runs_session_created", "agent_search_runs", ["session_id", "created_at"]
    )
    op.create_index(
        "ix_agent_search_runs_user_created", "agent_search_runs", ["user_id", "created_at"]
    )

    op.create_table(
        "agent_search_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("search_run_id", sa.Integer(), nullable=False),
        sa.Column("unit_type_id", sa.Integer(), nullable=True),
        sa.Column("property_id", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("score_breakdown_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["search_run_id"], ["agent_search_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_type_id"], ["unit_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "search_run_id", "unit_type_id", name="uq_agent_search_candidate_run_unit"
        ),
        sa.UniqueConstraint(
            "search_run_id", "rank", name="uq_agent_search_candidate_run_rank"
        ),
    )
    op.create_index(
        "ix_agent_search_candidates_search_run_id", "agent_search_candidates", ["search_run_id"]
    )
    op.create_index(
        "ix_agent_search_candidates_unit_type_id", "agent_search_candidates", ["unit_type_id"]
    )
    op.create_index(
        "ix_agent_search_candidates_property_id", "agent_search_candidates", ["property_id"]
    )
    op.create_index(
        "ix_agent_search_candidates_run_rank",
        "agent_search_candidates",
        ["search_run_id", "rank"],
    )


def downgrade() -> None:
    op.drop_table("agent_search_candidates")
    op.drop_table("agent_search_runs")
    op.drop_table("agent_user_memories")
    op.drop_table("agent_session_states")
    op.drop_index("ix_chat_sessions_session_kind", table_name="chat_sessions")
    op.drop_column("chat_sessions", "session_kind")

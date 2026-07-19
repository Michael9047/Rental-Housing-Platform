"""add compare sessions and compare messages

Revision ID: 20260713_0013
Revises: f7ca5aa62eee
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260713_0013"
down_revision: Union[str, None] = "f7ca5aa62eee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compare_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("property_ids", postgresql.JSON(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="balanced"),
        sa.Column(
            "status",
            sa.Enum("active", "completed", name="compare_session_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("result_cache", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_compare_sessions_id"), "compare_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_compare_sessions_user_id"), "compare_sessions", ["user_id"], unique=False)

    op.create_table(
        "compare_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_calls", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["compare_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_compare_messages_id"), "compare_messages", ["id"], unique=False)
    op.create_index(op.f("ix_compare_messages_session_id"), "compare_messages", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_compare_messages_session_id"), table_name="compare_messages")
    op.drop_index(op.f("ix_compare_messages_id"), table_name="compare_messages")
    op.drop_table("compare_messages")
    op.drop_index(op.f("ix_compare_sessions_user_id"), table_name="compare_sessions")
    op.drop_index(op.f("ix_compare_sessions_id"), table_name="compare_sessions")
    op.drop_table("compare_sessions")
    op.execute("DROP TYPE IF EXISTS compare_session_status")

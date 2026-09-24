"""add agent search workspace

Revision ID: 20260812_0041
Revises: 20260812_0040
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_0041"
down_revision: Union[str, None] = "20260812_0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("search_id", sa.String(length=96), nullable=True))
    op.add_column("chat_sessions", sa.Column("search_workspace", sa.JSON(), nullable=True))
    op.create_index(
        "ix_chat_sessions_search_id",
        "chat_sessions",
        ["search_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_search_id", table_name="chat_sessions")
    op.drop_column("chat_sessions", "search_workspace")
    op.drop_column("chat_sessions", "search_id")

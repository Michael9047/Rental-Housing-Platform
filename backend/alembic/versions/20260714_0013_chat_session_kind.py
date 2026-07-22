"""add kind to chat_sessions (区分 AI 管家会话与客服会话)

同时作为合并点：把 agent 购物车、房源管理升级、维修系统三条 head 合并。

Revision ID: 20260714_0013
Revises: 20260704_0011, 6df040ea2aeb, c73f8ff61bac
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0013"
down_revision: Union[str, Sequence[str], None] = (
    "20260704_0011",
    "6df040ea2aeb",
    "c73f8ff61bac",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="chat"),
    )
    op.create_index("ix_chat_sessions_kind", "chat_sessions", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_kind", table_name="chat_sessions")
    op.drop_column("chat_sessions", "kind")

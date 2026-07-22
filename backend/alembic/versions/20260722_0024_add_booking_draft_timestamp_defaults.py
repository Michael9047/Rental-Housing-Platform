"""为预订流程草稿时间戳增加数据库默认值。

Revision ID: 20260722_0024
Revises: 20260722_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260722_0024"
down_revision: str | None = "20260722_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("booking_flow_drafts", "created_at", server_default=sa.func.now())
    op.alter_column("booking_flow_drafts", "updated_at", server_default=sa.func.now())


def downgrade() -> None:
    op.alter_column("booking_flow_drafts", "updated_at", server_default=None)
    op.alter_column("booking_flow_drafts", "created_at", server_default=None)

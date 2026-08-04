"""为房源增加可用截止日期。

Revision ID: 20260722_0021
Revises: 20260722_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260722_0021"
down_revision: str | None = "20260722_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("available_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "available_until")

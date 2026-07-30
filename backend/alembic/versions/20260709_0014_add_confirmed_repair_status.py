"""add confirmed to repair_status enum

Revision ID: 20260709_0014
Revises: 20260709_0013
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260709_0014'
down_revision: Union[str, None] = '20260709_0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE repair_status ADD VALUE IF NOT EXISTS 'confirmed'")


def downgrade() -> None:
    # 无法从枚举中移除值，downgrade 不操作
    pass

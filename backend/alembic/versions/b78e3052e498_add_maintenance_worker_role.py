"""add maintenance_worker to user_role enum

Revision ID: b78e3052e498
Revises: 20260706_0011
Create Date: 2026-07-07 11:14:39.391965

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b78e3052e498'
down_revision: Union[str, None] = '20260706_0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'maintenance_worker'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums.
    # To revert, you'd need to create a new enum and swap, but that's destructive.
    pass

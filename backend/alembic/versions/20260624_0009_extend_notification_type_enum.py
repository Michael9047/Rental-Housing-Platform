"""extend notification_type enum

Revision ID: 20260624_0009
Revises: 20260623_0008
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0009"
down_revision: Union[str, None] = "20260623_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'booking_completed'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'payment_received'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'system'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an ENUM type.
    # To fully roll back, you would need to:
    #   1. Create a new enum type without the values
    #   2. Alter the column to use the new type
    #   3. Drop the old type
    # This is intentionally left as a no-op for safety.
    pass

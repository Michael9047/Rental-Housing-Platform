"""add_rent_period_to_unit_types

Revision ID: 8fcc418f50f5
Revises: 20260805_0101
Create Date: 2026-08-05 23:06:12.181477

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8fcc418f50f5'
down_revision: Union[str, None] = '20260805_0101'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE rent_period AS ENUM ('monthly', 'weekly')")
    op.add_column('unit_types',
        sa.Column('rent_period', sa.Enum('monthly', 'weekly', name='rent_period'),
                  nullable=False, server_default='monthly'))


def downgrade() -> None:
    op.drop_column('unit_types', 'rent_period')
    op.execute("DROP TYPE rent_period")

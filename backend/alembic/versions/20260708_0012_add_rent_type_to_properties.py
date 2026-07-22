"""Add rent_type field to properties

Revision ID: 20260708_0012
Revises: 20260706_0011
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260708_0012'
down_revision: Union[str, None] = '20260706_0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE rent_type AS ENUM ('monthly', 'quarterly', 'yearly')")
    op.add_column('properties', sa.Column('rent_type', sa.Enum('monthly', 'quarterly', 'yearly', name='rent_type'), nullable=False, server_default='monthly'))


def downgrade() -> None:
    op.drop_column('properties', 'rent_type')
    op.execute("DROP TYPE rent_type")

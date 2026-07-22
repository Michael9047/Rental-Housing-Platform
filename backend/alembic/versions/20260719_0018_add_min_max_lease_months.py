"""Add min_lease_months and max_lease_months to properties

Revision ID: 20260719_0018
Revises: d52d47faa4b4
Create Date: 2026-07-19 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260719_0018'
down_revision: Union[str, None] = 'd52d47faa4b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('properties', sa.Column('min_lease_months', sa.Integer(), nullable=False, server_default='12'))
    op.add_column('properties', sa.Column('max_lease_months', sa.Integer(), nullable=True, server_default='60'))


def downgrade() -> None:
    op.drop_column('properties', 'max_lease_months')
    op.drop_column('properties', 'min_lease_months')

"""add_missing_room_columns

Revision ID: 5c56852684be
Revises: bf7f24872cf4
Create Date: 2026-07-24 14:53:01.276602

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '5c56852684be'
down_revision: Union[str, None] = 'bf7f24872cf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('properties', sa.Column('safety_score', sa.Numeric(3, 2), nullable=True))
    op.add_column('properties', sa.Column('institute_name', sa.String(200), nullable=True))
    op.add_column('properties', sa.Column('institute_amenities', sa.Text, nullable=True))
    op.add_column('properties', sa.Column('female_only', sa.Boolean, nullable=True, server_default=sa.text('false')))
    op.add_column('properties', sa.Column('currency', sa.String(3), nullable=True, server_default=sa.text("'CNY'")))


def downgrade() -> None:
    op.drop_column('properties', 'currency')
    op.drop_column('properties', 'female_only')
    op.drop_column('properties', 'institute_amenities')
    op.drop_column('properties', 'institute_name')
    op.drop_column('properties', 'safety_score')

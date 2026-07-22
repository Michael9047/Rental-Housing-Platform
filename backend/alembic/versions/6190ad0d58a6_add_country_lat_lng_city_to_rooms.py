"""add country lat lng city to rooms

Revision ID: 6190ad0d58a6
Revises: cc65d383b732
Create Date: 2026-07-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '6190ad0d58a6'
down_revision: Union[str, None] = 'cc65d383b732'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('country', sa.String(length=100), nullable=True))
    op.add_column('rooms', sa.Column('latitude', sa.Numeric(9, 6), nullable=True))
    op.add_column('rooms', sa.Column('longitude', sa.Numeric(9, 6), nullable=True))
    op.add_column('rooms', sa.Column('city', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('rooms', 'city')
    op.drop_column('rooms', 'longitude')
    op.drop_column('rooms', 'latitude')
    op.drop_column('rooms', 'country')

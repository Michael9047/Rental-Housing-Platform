"""add room_number to rooms

Revision ID: fe7b76a287e9
Revises: 3ef8cf1ad777
Create Date: 2026-07-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'fe7b76a287e9'
down_revision: Union[str, None] = '3ef8cf1ad777'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('room_number', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('rooms', 'room_number')

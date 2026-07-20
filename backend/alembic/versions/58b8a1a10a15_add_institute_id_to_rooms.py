"""add institute_id to rooms

Revision ID: 58b8a1a10a15
Revises: 6190ad0d58a6
Create Date: 2026-07-20 21:26:49.620718

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '58b8a1a10a15'
down_revision: Union[str, None] = '6190ad0d58a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('institute_id', sa.Integer(), nullable=True))
    op.create_index('ix_rooms_institute_id', 'rooms', ['institute_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_rooms_institute_id', 'rooms')
    op.drop_column('rooms', 'institute_id')

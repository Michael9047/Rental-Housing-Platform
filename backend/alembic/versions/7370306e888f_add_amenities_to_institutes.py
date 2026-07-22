"""add amenities to institutes

Revision ID: 7370306e888f
Revises: 08835d9dd925
Create Date: 2026-07-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7370306e888f'
down_revision: Union[str, None] = '08835d9dd925'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('institutes', sa.Column('amenities', sa.ARRAY(sa.String(30)), nullable=True))


def downgrade() -> None:
    op.drop_column('institutes', 'amenities')

"""add npc to institutes

Revision ID: 20260723_npc
Revises: ntf_delivery_001
Create Date: 2026-07-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260723_npc'
down_revision: Union[str, None] = 'ntf_delivery_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('institutes', sa.Column('npc', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('institutes', 'npc')

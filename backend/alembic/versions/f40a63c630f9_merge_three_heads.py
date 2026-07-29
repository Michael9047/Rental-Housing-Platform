"""merge_three_heads

Revision ID: f40a63c630f9
Revises: 20260709_0014, 20260722_0033, 20260723_npc
Create Date: 2026-07-27 14:48:36.284248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f40a63c630f9'
down_revision: Union[str, None] = ('20260709_0014', '20260722_0033', '20260723_npc')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

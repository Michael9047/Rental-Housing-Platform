"""merge_all_heads_20260724

Revision ID: bf7f24872cf4
Revises: 20260709_0014, 20260722_0033, 20260723_npc
Create Date: 2026-07-24 14:53:00.562360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bf7f24872cf4'
down_revision: Union[str, None] = ('20260709_0014', '20260722_0033', '20260723_npc')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""merge_all_heads

Revision ID: d625946f53a4
Revises: 20260709_0014, 20260722_0033, 20260723_npc
Create Date: 2026-07-28 10:42:02.725391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd625946f53a4'
down_revision: Union[str, None] = ('20260709_0014', '20260722_0033', '20260723_npc')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

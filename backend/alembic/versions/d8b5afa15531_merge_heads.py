"""merge_heads

Revision ID: d8b5afa15531
Revises: 20260704_0011, 6df040ea2aeb, c73f8ff61bac
Create Date: 2026-07-12 15:01:32.668789

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8b5afa15531'
down_revision: Union[str, None] = ('20260704_0011', '6df040ea2aeb', 'c73f8ff61bac')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

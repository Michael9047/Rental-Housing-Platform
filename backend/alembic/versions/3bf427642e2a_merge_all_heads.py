"""merge_all_heads

Revision ID: 3bf427642e2a
Revises: 20260704_0011, 20260714_0014, 6df040ea2aeb, c73f8ff61bac
Create Date: 2026-07-15 14:27:16.702226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3bf427642e2a'
down_revision: Union[str, None] = ('20260704_0011', '20260714_0014', '6df040ea2aeb', 'c73f8ff61bac')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

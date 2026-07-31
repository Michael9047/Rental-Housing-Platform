"""merge_main_into_branch

Revision ID: 4c660ac0e3e3
Revises: 9bc74a9fddef, a90de4c088bd
Create Date: 2026-07-31 12:57:02.391399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c660ac0e3e3'
down_revision: Union[str, None] = ('9bc74a9fddef', 'a90de4c088bd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

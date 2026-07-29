"""merge pr39 three-layer-id-system into main

Revision ID: 9bc74a9fddef
Revises: 07de8c996fa3, f7e8d9c0b1a2
Create Date: 2026-07-29 14:54:13.412160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9bc74a9fddef'
down_revision: Union[str, None] = ('07de8c996fa3', 'f7e8d9c0b1a2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""merge dual heads: country field + room_number_floor

Revision ID: 349ef87cce3a
Revises: 20260706_0011, 4aea0d4cf47c
Create Date: 2026-07-07 15:46:37.368204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '349ef87cce3a'
down_revision: Union[str, None] = ('20260706_0011', '4aea0d4cf47c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

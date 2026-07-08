"""merge room_number_floor into main

Revision ID: 4aea0d4cf47c
Revises: 20260706_0012, 5ac4aa5f38f4
Create Date: 2026-07-06 18:27:29.434898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4aea0d4cf47c'
down_revision: Union[str, None] = ('20260706_0012', '5ac4aa5f38f4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

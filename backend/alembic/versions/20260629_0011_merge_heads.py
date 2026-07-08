"""merge institutes and user_favorites heads

Revision ID: 20260629_0011
Revises: 20260626_0010, 20260629_0009
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260629_0011"
down_revision: Union[str, None] = ("20260626_0010", "20260629_0009")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""add room_number and floor to properties

Revision ID: 20260706_0012
Revises: 20260629_0011
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260706_0012"
down_revision: Union[str, None] = "20260629_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("room_number", sa.String(20), nullable=True))
    op.add_column("properties", sa.Column("floor", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "floor")
    op.drop_column("properties", "room_number")

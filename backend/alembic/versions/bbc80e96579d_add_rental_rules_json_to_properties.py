"""add_rental_rules_json_to_properties

Revision ID: bbc80e96579d
Revises: 3bf427642e2a
Create Date: 2026-07-15 15:24:06.117379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bbc80e96579d'
down_revision: Union[str, None] = '3bf427642e2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("rental_rules", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "rental_rules")

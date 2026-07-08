"""add country field to properties

Revision ID: 20260706_0011
Revises: 5ac4aa5f38f4
Create Date: 2026-07-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260706_0011"
down_revision: Union[str, None] = "5ac4aa5f38f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column("country", sa.String(2), nullable=False, server_default="CN"),
    )
    op.create_index("ix_properties_country", "properties", ["country"])


def downgrade() -> None:
    op.drop_index("ix_properties_country", table_name="properties")
    op.drop_column("properties", "country")

"""扩展公寓国家字段，支持完整英文国家名称。

Revision ID: 20260813_0045
Revises: 20260813_0044
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0045"
down_revision = "20260813_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "institutes",
        "country",
        existing_type=sa.String(length=10),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "institutes",
        "country",
        existing_type=sa.String(length=100),
        type_=sa.String(length=10),
        existing_nullable=True,
    )

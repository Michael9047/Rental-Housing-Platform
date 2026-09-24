"""add tenant phone country codes

Revision ID: 20260813_0042
Revises: 20260812_0041
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_0042"
down_revision: Union[str, None] = "20260812_0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("phone_country_code", sa.String(length=8), nullable=True))
    op.add_column("tenants", sa.Column("emergency_phone_country_code", sa.String(length=8), nullable=True))
    op.execute("UPDATE tenants SET phone_country_code = '+86' WHERE phone_country_code IS NULL")
    op.execute(
        "UPDATE tenants SET emergency_phone_country_code = '+86' "
        "WHERE emergency_phone IS NOT NULL AND emergency_phone_country_code IS NULL"
    )


def downgrade() -> None:
    op.drop_column("tenants", "emergency_phone_country_code")
    op.drop_column("tenants", "phone_country_code")

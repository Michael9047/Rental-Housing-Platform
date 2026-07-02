"""add booking contract info workflow fields

Revision ID: 20260702_0012
Revises: 20260628_0011
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260702_0012"
down_revision: Union[str, None] = "20260628_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("contract_real_name", sa.String(length=100), nullable=True))
    op.add_column("bookings", sa.Column("contract_id_card_no", sa.String(length=32), nullable=True))
    op.add_column("bookings", sa.Column("contract_phone", sa.String(length=32), nullable=True))
    op.add_column("bookings", sa.Column("lease_start_date", sa.String(length=32), nullable=True))
    op.add_column("bookings", sa.Column("lease_end_date", sa.String(length=32), nullable=True))
    op.add_column("bookings", sa.Column("contract_extra_terms", sa.Text(), nullable=True))
    op.add_column(
        "bookings",
        sa.Column("contract_info_status", sa.String(length=30), nullable=False, server_default="missing"),
    )
    op.add_column(
        "bookings",
        sa.Column("contract_landlord_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bookings", "contract_landlord_confirmed_at")
    op.drop_column("bookings", "contract_info_status")
    op.drop_column("bookings", "contract_extra_terms")
    op.drop_column("bookings", "lease_end_date")
    op.drop_column("bookings", "lease_start_date")
    op.drop_column("bookings", "contract_phone")
    op.drop_column("bookings", "contract_id_card_no")
    op.drop_column("bookings", "contract_real_name")

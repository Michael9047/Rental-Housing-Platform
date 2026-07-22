"""补齐预约租期字段并为合同增加房源快照。

Revision ID: 20260722_0019
Revises: 20260722_0018
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "20260722_0019"
down_revision: Union[str, None] = "20260722_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    booking_columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("bookings")
    }
    if "lease_months" not in booking_columns:
        op.add_column(
            "bookings",
            sa.Column("lease_months", sa.Integer(), nullable=True),
        )
    if "total_rent" not in booking_columns:
        op.add_column(
            "bookings",
            sa.Column("total_rent", sa.Integer(), nullable=True),
        )
    if "application_data" not in booking_columns:
        op.add_column(
            "bookings",
            sa.Column(
                "application_data",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    contract_columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("contracts")
    }
    if "property_snapshot" not in contract_columns:
        op.add_column(
            "contracts",
            sa.Column(
                "property_snapshot",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    contract_columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("contracts")
    }
    if "property_snapshot" in contract_columns:
        op.drop_column("contracts", "property_snapshot")

    booking_columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("bookings")
    }
    if "application_data" in booking_columns:
        op.drop_column("bookings", "application_data")
    if "total_rent" in booking_columns:
        op.drop_column("bookings", "total_rent")
    if "lease_months" in booking_columns:
        op.drop_column("bookings", "lease_months")

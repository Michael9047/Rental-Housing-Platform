"""deposit, contract, payment, and POI tables

Revision ID: 20260623_0008
Revises: 20260622_0007
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260623_0008"
down_revision: Union[str, None] = "20260622_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Property: new columns ---
    op.add_column("properties", sa.Column("deposit_amount", sa.Integer(), nullable=True, server_default="1000"))
    op.add_column("properties", sa.Column("service_fee_rate", sa.Float(), nullable=True, server_default="0.10"))

    # --- Booking: new columns ---
    op.add_column("bookings", sa.Column("deposit_amount", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("service_fee", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("deposit_status", sa.String(length=20), nullable=False, server_default="unpaid"))
    op.add_column("bookings", sa.Column("payment_transaction_id", sa.String(length=255), nullable=True))

    # --- Contracts ---
    op.create_table(
        "contracts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("template_name", sa.String(length=100), nullable=False, server_default="standard_lease"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_contracts_booking_id"), "contracts", ["booking_id"], unique=False)
    op.create_index(op.f("ix_contracts_tenant_id"), "contracts", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_contracts_property_id"), "contracts", ["property_id"], unique=False)
    op.create_index(op.f("ix_contracts_id"), "contracts", ["id"], unique=False)

    # --- Payments ---
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(length=50), nullable=False, server_default="wechat_pay"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_payments_booking_id"), "payments", ["booking_id"], unique=False)
    op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"], unique=False)
    op.create_index(op.f("ix_payments_id"), "payments", ["id"], unique=False)

    # --- Property POIs ---
    op.create_table(
        "property_pois",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("poi_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_property_pois_property_id"), "property_pois", ["property_id"], unique=False)
    op.create_index(op.f("ix_property_pois_id"), "property_pois", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_property_pois_id"), table_name="property_pois")
    op.drop_index(op.f("ix_property_pois_property_id"), table_name="property_pois")
    op.drop_table("property_pois")

    op.drop_index(op.f("ix_payments_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_user_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_booking_id"), table_name="payments")
    op.drop_table("payments")

    op.drop_index(op.f("ix_contracts_id"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_property_id"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_tenant_id"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_booking_id"), table_name="contracts")
    op.drop_table("contracts")

    op.drop_column("bookings", "payment_transaction_id")
    op.drop_column("bookings", "deposit_status")
    op.drop_column("bookings", "service_fee")
    op.drop_column("bookings", "deposit_amount")

    op.drop_column("properties", "service_fee_rate")
    op.drop_column("properties", "deposit_amount")
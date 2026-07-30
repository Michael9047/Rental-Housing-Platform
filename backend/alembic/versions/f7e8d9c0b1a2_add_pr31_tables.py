"""Add PR31 booking-flow tables.

Revision ID: f7e8d9c0b1a2
Revises: 9834aa635353
Create Date: 2026-07-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f7e8d9c0b1a2'
down_revision: Union[str, None] = '9834aa635353'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. booking_flow_drafts ──────────────────────
    op.create_table("booking_flow_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.String(length=32), nullable=False, server_default="move_in_date"),
        sa.Column("move_in_date", sa.String(length=32), nullable=True),
        sa.Column("lease_months", sa.Integer(), nullable=True),
        sa.Column("personal_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("emergency_contact", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_booking_flow_drafts_id", "booking_flow_drafts", ["id"])
    op.create_index("ix_booking_flow_drafts_property_id", "booking_flow_drafts", ["property_id"])
    op.create_index("ix_booking_flow_drafts_user_id", "booking_flow_drafts", ["user_id"])

    # ── 2. contract_signatures ──────────────────────
    op.create_table("contract_signatures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agreement_id", sa.String(length=36), nullable=False),
        sa.Column("agreement_version", sa.Integer(), nullable=False),
        sa.Column("agreement_content_hash", sa.String(length=64), nullable=False),
        sa.Column("tenant_user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_name", sa.String(length=200), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("property_timezone", sa.String(length=64), nullable=False),
        sa.Column("consent_text_version", sa.String(length=32), nullable=False),
        sa.Column("signature_object_key", sa.String(length=500), nullable=False),
        sa.Column("signature_hash", sa.String(length=64), nullable=False),
        sa.Column("signed_pdf_object_key", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key")
    )
    op.create_index("ix_contract_signatures_agreement_id", "contract_signatures", ["agreement_id"], unique=True)
    op.create_index("ix_contract_signatures_tenant_user_id", "contract_signatures", ["tenant_user_id"])

    # ── 3. payment_webhook_events ───────────────────
    op.create_table("payment_webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_id", name="uq_payment_webhook_provider_event")
    )

    # ── 4. policy_consents ──────────────────────────
    op.create_table("policy_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("policy_key", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_policy_consents_booking_id", "policy_consents", ["booking_id"])
    op.create_index("ix_policy_consents_id", "policy_consents", ["id"])
    op.create_index("ix_policy_consents_user_id", "policy_consents", ["user_id"])

    # ── 5. contracts new columns ────────────────────
    op.add_column("contracts", sa.Column("agreement_number", sa.String(length=64), nullable=True))
    op.add_column("contracts", sa.Column("template_version", sa.String(length=32), nullable=False, server_default="2026.1"))
    op.add_column("contracts", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("contracts", sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("contracts", sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contracts", sa.Column("pdf_status", sa.String(length=20), nullable=False, server_default="not_generated"))
    op.add_column("contracts", sa.Column("pdf_last_error", sa.String(length=500), nullable=True))
    op.create_index("ix_contracts_agreement_number", "contracts", ["agreement_number"], unique=True)
    op.create_index("ix_contracts_content_hash", "contracts", ["content_hash"])

    # ── 6. payments new columns ─────────────────────
    op.add_column("payments", sa.Column("order_id", sa.String(length=64), nullable=True))
    op.add_column("payments", sa.Column("payment_attempt_id", sa.String(length=64), nullable=True))
    op.add_column("payments", sa.Column("settlement_currency", sa.String(length=3), nullable=False, server_default="CNY"))
    op.add_column("payments", sa.Column("settlement_amount_minor", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("cny_reference_amount_minor", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("property_currency", sa.String(length=3), nullable=False, server_default="CNY"))
    op.add_column("payments", sa.Column("exchange_rate", sa.Numeric(precision=24, scale=12), nullable=False, server_default="1"))
    op.add_column("payments", sa.Column("exchange_rate_source", sa.String(length=200), nullable=False, server_default="platform snapshot"))
    op.add_column("payments", sa.Column("exchange_rate_timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("payments", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now() + interval '24 hours'")))
    op.add_column("payments", sa.Column("provider", sa.String(length=40), nullable=False, server_default="mock_hosted"))
    op.add_column("payments", sa.Column("provider_payment_id", sa.String(length=100), nullable=True))
    op.add_column("payments", sa.Column("provider_checkout_id", sa.String(length=100), nullable=True))
    op.add_column("payments", sa.Column("provider_merchant_account", sa.String(length=100), nullable=True))
    op.add_column("payments", sa.Column("checkout_url", sa.String(length=500), nullable=True))
    op.add_column("payments", sa.Column("idempotency_key", sa.String(length=100), nullable=True))
    op.add_column("payments", sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"))
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=True)
    op.create_index("ix_payments_payment_attempt_id", "payments", ["payment_attempt_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_payments_payment_attempt_id", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_column("payments", "snapshot")
    op.drop_column("payments", "idempotency_key")
    op.drop_column("payments", "checkout_url")
    op.drop_column("payments", "provider_merchant_account")
    op.drop_column("payments", "provider_checkout_id")
    op.drop_column("payments", "provider_payment_id")
    op.drop_column("payments", "provider")
    op.drop_column("payments", "expires_at")
    op.drop_column("payments", "exchange_rate_timestamp")
    op.drop_column("payments", "exchange_rate_source")
    op.drop_column("payments", "exchange_rate")
    op.drop_column("payments", "property_currency")
    op.drop_column("payments", "cny_reference_amount_minor")
    op.drop_column("payments", "settlement_amount_minor")
    op.drop_column("payments", "settlement_currency")
    op.drop_column("payments", "payment_attempt_id")
    op.drop_column("payments", "order_id")
    op.drop_index("ix_contracts_content_hash", table_name="contracts")
    op.drop_index("ix_contracts_agreement_number", table_name="contracts")
    op.drop_column("contracts", "pdf_last_error")
    op.drop_column("contracts", "pdf_status")
    op.drop_column("contracts", "generated_at")
    op.drop_column("contracts", "snapshot")
    op.drop_column("contracts", "content_hash")
    op.drop_column("contracts", "template_version")
    op.drop_column("contracts", "agreement_number")
    op.drop_index("ix_policy_consents_user_id", table_name="policy_consents")
    op.drop_index("ix_policy_consents_id", table_name="policy_consents")
    op.drop_index("ix_policy_consents_booking_id", table_name="policy_consents")
    op.drop_table("policy_consents")
    op.drop_table("payment_webhook_events")
    op.drop_index("ix_contract_signatures_tenant_user_id", table_name="contract_signatures")
    op.drop_index("ix_contract_signatures_agreement_id", table_name="contract_signatures")
    op.drop_table("contract_signatures")
    op.drop_index("ix_booking_flow_drafts_user_id", table_name="booking_flow_drafts")
    op.drop_index("ix_booking_flow_drafts_property_id", table_name="booking_flow_drafts")
    op.drop_index("ix_booking_flow_drafts_id", table_name="booking_flow_drafts")
    op.drop_table("booking_flow_drafts")


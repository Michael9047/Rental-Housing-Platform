"""增加测试模式支付订单快照和 webhook 幂等记录。

Revision ID: 20260722_0026
Revises: 20260722_0025
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260722_0026"
down_revision = "20260722_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("payment_expires_at", sa.DateTime(timezone=True)))
    columns = [
        sa.Column("settlement_currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("settlement_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cny_reference_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("property_currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("exchange_rate", sa.Numeric(24, 12), nullable=False, server_default="1"),
        sa.Column("exchange_rate_source", sa.String(200), nullable=False, server_default="legacy"),
        sa.Column("exchange_rate_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(40), nullable=False, server_default="mock_hosted"),
        sa.Column("provider_payment_id", sa.String(100)), sa.Column("provider_checkout_id", sa.String(100)),
        sa.Column("provider_merchant_account", sa.String(100)), sa.Column("checkout_url", sa.String(500)),
        sa.Column("idempotency_key", sa.String(100)),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    ]
    for column in columns: op.add_column("payments", column)
    op.execute("UPDATE payments SET exchange_rate_timestamp=created_at, expires_at=created_at + interval '24 hours', idempotency_key='legacy-' || id")
    for name in ("exchange_rate_timestamp", "expires_at", "idempotency_key"):
        op.alter_column("payments", name, nullable=False)
    op.create_unique_constraint("uq_payments_provider_payment_id", "payments", ["provider_payment_id"])
    op.create_unique_constraint("uq_payments_provider_checkout_id", "payments", ["provider_checkout_id"])
    op.create_unique_constraint("uq_payments_idempotency_key", "payments", ["idempotency_key"])
    op.create_table("payment_webhook_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("provider", sa.String(40), nullable=False), sa.Column("event_id", sa.String(100), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("provider", "event_id", name="uq_payment_webhook_provider_event"))


def downgrade() -> None:
    op.drop_table("payment_webhook_events")
    for name in ["snapshot", "idempotency_key", "checkout_url", "provider_merchant_account", "provider_checkout_id", "provider_payment_id", "provider", "expires_at", "exchange_rate_timestamp", "exchange_rate_source", "exchange_rate", "property_currency", "cny_reference_amount_minor", "settlement_amount_minor", "settlement_currency"]:
        op.drop_column("payments", name)
    op.drop_column("bookings", "payment_expires_at")

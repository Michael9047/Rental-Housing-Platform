"""补全所有缺失列和表 — 模型↔数据库同步"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSON, JSONB

revision: str = "20260730_0036"
down_revision: Union[str, None] = "20260730_0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 缺失列 ──

    # bookings
    op.add_column("bookings", sa.Column("payment_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("inventory_reserved", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # contracts
    op.add_column("contracts", sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))

    # notifications (entity_id/order_id/agreement_id 都是 String 不是 Integer)
    op.add_column("notifications", sa.Column("body", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("entity_type", sa.String(40), nullable=True))
    op.add_column("notifications", sa.Column("entity_id", sa.String(100), nullable=True))
    op.add_column("notifications", sa.Column("order_id", sa.String(64), nullable=True))
    op.add_column("notifications", sa.Column("agreement_id", sa.String(100), nullable=True))
    op.add_column("notifications", sa.Column("property_id", sa.Integer(), nullable=True))

    # payments
    op.add_column("payments", sa.Column("out_trade_no", sa.String(64), nullable=True))
    op.add_column("payments", sa.Column("trade_state_desc", sa.String(256), nullable=True))
    op.add_column("payments", sa.Column("trade_state", sa.String(32), nullable=True))

    # repair_workers
    op.add_column("repair_workers", sa.Column("scope", sa.String(20), nullable=True))

    # room_transfers
    op.add_column("room_transfers", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # unit_types
    op.add_column("unit_types", sa.Column("embedding", sa.Text(), nullable=True))

    # rooms
    op.add_column("rooms", sa.Column("furnished", sa.Boolean(), nullable=True))
    op.add_column("rooms", sa.Column("bed_type", sa.String(30), nullable=True))
    op.add_column("rooms", sa.Column("institute_id", sa.Integer(), nullable=True))
    op.add_column("rooms", sa.Column("utilities_included", ARRAY(sa.String(50)), nullable=True))
    op.add_column("rooms", sa.Column("max_occupancy", sa.Integer(), nullable=True))
    op.add_column("rooms", sa.Column("floor_plan_url", sa.String(500), nullable=True))
    op.add_column("rooms", sa.Column("gender_allocation", sa.String(20), nullable=True))
    op.add_column("rooms", sa.Column("bathroom_type", sa.String(30), nullable=True))
    op.add_column("rooms", sa.Column("internet_type", sa.String(30), nullable=True))

    # ── 缺失表 ──

    # institute_pois (PK = institute_id, 不是独立 id 列)
    op.create_table(
        "institute_pois",
        sa.Column("institute_id", sa.Integer(), sa.ForeignKey("institutes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("poi_data", JSON, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("map_poi_data", JSON, nullable=True),
        sa.Column("safety_data", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # notification_outbox (id = UUID String(36))
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_key", sa.String(180), unique=True, index=True, nullable=False),
        sa.Column("event_type", sa.String(60), index=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), index=True, nullable=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default=sa.text("'email'")),
        sa.Column("template_version", sa.String(20), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'"), index=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_outbox")
    op.drop_table("institute_pois")

    op.drop_column("rooms", "internet_type")
    op.drop_column("rooms", "bathroom_type")
    op.drop_column("rooms", "gender_allocation")
    op.drop_column("rooms", "floor_plan_url")
    op.drop_column("rooms", "max_occupancy")
    op.drop_column("rooms", "utilities_included")
    op.drop_column("rooms", "institute_id")
    op.drop_column("rooms", "bed_type")
    op.drop_column("rooms", "furnished")

    op.drop_column("unit_types", "embedding")
    op.drop_column("room_transfers", "updated_at")
    op.drop_column("repair_workers", "scope")
    op.drop_column("payments", "trade_state")
    op.drop_column("payments", "trade_state_desc")
    op.drop_column("payments", "out_trade_no")
    op.drop_column("notifications", "property_id")
    op.drop_column("notifications", "agreement_id")
    op.drop_column("notifications", "order_id")
    op.drop_column("notifications", "entity_id")
    op.drop_column("notifications", "entity_type")
    op.drop_column("notifications", "body")
    op.drop_column("contracts", "version")
    op.drop_column("bookings", "inventory_reserved")
    op.drop_column("bookings", "payment_expires_at")

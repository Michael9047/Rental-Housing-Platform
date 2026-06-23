"""booking and notification tables

Revision ID: 20260620_0004
Revises: 20260620_0003
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260620_0004"
down_revision: Union[str, None] = "20260620_0003_property_images"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

booking_status = sa.Enum("pending", "approved", "rejected", "cancelled", "completed", name="booking_status")
notification_type = sa.Enum("booking_created", "booking_approved", "booking_rejected", "booking_cancelled", name="notification_type")


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("landlord_id", sa.Integer(), nullable=False),
        sa.Column("status", booking_status, nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("scheduled_date", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["landlord_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_bookings_id"), "bookings", ["id"], unique=False)
    op.create_index(op.f("ix_bookings_tenant_id"), "bookings", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_bookings_property_id"), "bookings", ["property_id"], unique=False)
    op.create_index(op.f("ix_bookings_landlord_id"), "bookings", ["landlord_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_bookings_landlord_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_property_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_tenant_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_id"), table_name="bookings")
    op.drop_table("bookings")
    op.execute("DROP TYPE IF EXISTS notification_type")
    op.execute("DROP TYPE IF EXISTS booking_status")

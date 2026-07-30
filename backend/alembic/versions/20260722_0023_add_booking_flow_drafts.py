"""增加认证用户预订流程草稿。

Revision ID: 20260722_0023
Revises: 20260722_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260722_0023"
down_revision: str | None = "20260722_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "booking_flow_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("move_in_date", sa.Date(), nullable=True),
        sa.Column("lease_months", sa.Integer(), nullable=True),
        sa.Column("current_step", sa.String(length=32), nullable=False),
        sa.Column("personal_info", sa.JSON(), nullable=True),
        sa.Column("emergency_contact", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "property_id", name="uq_booking_flow_drafts_user_property"),
    )
    op.create_index("ix_booking_flow_drafts_user_id", "booking_flow_drafts", ["user_id"])
    op.create_index("ix_booking_flow_drafts_property_id", "booking_flow_drafts", ["property_id"])


def downgrade() -> None:
    op.drop_index("ix_booking_flow_drafts_property_id", table_name="booking_flow_drafts")
    op.drop_index("ix_booking_flow_drafts_user_id", table_name="booking_flow_drafts")
    op.drop_table("booking_flow_drafts")

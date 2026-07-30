"""增加政策同意证据表。

Revision ID: 20260722_0022
Revises: 20260722_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260722_0022"
down_revision: str | None = "20260722_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_key", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("agreed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("booking_id", "policy_key", name="uq_policy_consents_booking_key"),
    )
    op.create_index("ix_policy_consents_booking_id", "policy_consents", ["booking_id"])
    op.create_index("ix_policy_consents_user_id", "policy_consents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_consents_user_id", table_name="policy_consents")
    op.drop_index("ix_policy_consents_booking_id", table_name="policy_consents")
    op.drop_table("policy_consents")

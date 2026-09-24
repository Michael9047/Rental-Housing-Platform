"""记录房源进入回收站的级联批次。

Revision ID: 20260813_0044
Revises: 20260813_0043
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260813_0044"
down_revision = "20260813_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listing_deletion_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("building_status", sa.String(length=30), nullable=False),
        sa.Column("unit_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_listing_deletion_batches_building_id", "listing_deletion_batches", ["building_id"])


def downgrade() -> None:
    op.drop_index("ix_listing_deletion_batches_building_id", table_name="listing_deletion_batches")
    op.drop_table("listing_deletion_batches")

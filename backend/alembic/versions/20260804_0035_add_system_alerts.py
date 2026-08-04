"""add_system_alerts

Revision ID: 20260804_0035
Revises: bf7f24872cf4
Create Date: 2026-08-04 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260804_0035"
down_revision: Union[str, None] = "bf7f24872cf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("high", "medium", "low", name="system_alert_severity"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "acknowledged", "resolved", name="system_alert_status"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=60), nullable=True),
        sa.Column("action_label", sa.String(length=60), nullable=True),
        sa.Column("action_resource_id", sa.String(length=120), nullable=True),
        sa.Column("extra", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("reported_by_id", sa.Integer(), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reported_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_alerts_id"), "system_alerts", ["id"], unique=False)
    op.create_index(op.f("ix_system_alerts_category"), "system_alerts", ["category"], unique=False)
    op.create_index(op.f("ix_system_alerts_severity"), "system_alerts", ["severity"], unique=False)
    op.create_index(op.f("ix_system_alerts_source"), "system_alerts", ["source"], unique=False)
    op.create_index(op.f("ix_system_alerts_source_id"), "system_alerts", ["source_id"], unique=False)
    op.create_index(op.f("ix_system_alerts_status"), "system_alerts", ["status"], unique=False)
    op.create_index(op.f("ix_system_alerts_reported_by_id"), "system_alerts", ["reported_by_id"], unique=False)
    op.create_index(op.f("ix_system_alerts_resolved_by_id"), "system_alerts", ["resolved_by_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_system_alerts_resolved_by_id"), table_name="system_alerts")
    op.drop_index(op.f("ix_system_alerts_reported_by_id"), table_name="system_alerts")
    op.drop_index(op.f("ix_system_alerts_status"), table_name="system_alerts")
    op.drop_index(op.f("ix_system_alerts_source_id"), table_name="system_alerts")
    op.drop_index(op.f("ix_system_alerts_source"), table_name="system_alerts")
    op.drop_index(op.f("ix_system_alerts_severity"), table_name="system_alerts")
    op.drop_index(op.f("ix_system_alerts_category"), table_name="system_alerts")
    op.drop_index(op.f("ix_system_alerts_id"), table_name="system_alerts")
    op.drop_table("system_alerts")
    op.execute("DROP TYPE IF EXISTS system_alert_status")
    op.execute("DROP TYPE IF EXISTS system_alert_severity")

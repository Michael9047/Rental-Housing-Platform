"""add_system_alert_process_records

Revision ID: 20260805_0036
Revises: 20260804_0035
Create Date: 2026-08-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260805_0036"
down_revision: Union[str, None] = "20260804_0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_alert_process_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_key", sa.String(length=160), nullable=False),
        sa.Column("system_alert_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status_before", sa.String(length=80), nullable=True),
        sa.Column("status_after", sa.String(length=80), nullable=True),
        sa.Column("handled_by_id", sa.Integer(), nullable=True),
        sa.Column("extra", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["handled_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["system_alert_id"], ["system_alerts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_alert_process_records_id"), "system_alert_process_records", ["id"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_alert_key"), "system_alert_process_records", ["alert_key"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_system_alert_id"), "system_alert_process_records", ["system_alert_id"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_category"), "system_alert_process_records", ["category"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_severity"), "system_alert_process_records", ["severity"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_source"), "system_alert_process_records", ["source"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_source_id"), "system_alert_process_records", ["source_id"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_action_type"), "system_alert_process_records", ["action_type"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_handled_by_id"), "system_alert_process_records", ["handled_by_id"], unique=False)
    op.create_index(op.f("ix_system_alert_process_records_created_at"), "system_alert_process_records", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_system_alert_process_records_created_at"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_handled_by_id"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_action_type"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_source_id"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_source"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_severity"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_category"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_system_alert_id"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_alert_key"), table_name="system_alert_process_records")
    op.drop_index(op.f("ix_system_alert_process_records_id"), table_name="system_alert_process_records")
    op.drop_table("system_alert_process_records")

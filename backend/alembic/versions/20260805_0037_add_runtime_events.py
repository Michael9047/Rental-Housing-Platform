"""add_runtime_events

Revision ID: 20260805_0037
Revises: 20260805_0036
Create Date: 2026-08-05 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260805_0037"
down_revision: Union[str, None] = "20260805_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runtime_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=12), nullable=True),
        sa.Column("path", sa.String(length=240), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runtime_events_id"), "runtime_events", ["id"], unique=False)
    op.create_index(op.f("ix_runtime_events_level"), "runtime_events", ["level"], unique=False)
    op.create_index(op.f("ix_runtime_events_event_type"), "runtime_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_runtime_events_path"), "runtime_events", ["path"], unique=False)
    op.create_index(op.f("ix_runtime_events_status_code"), "runtime_events", ["status_code"], unique=False)
    op.create_index(op.f("ix_runtime_events_request_id"), "runtime_events", ["request_id"], unique=False)
    op.create_index(op.f("ix_runtime_events_user_id"), "runtime_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_runtime_events_handled_at"), "runtime_events", ["handled_at"], unique=False)
    op.create_index(op.f("ix_runtime_events_created_at"), "runtime_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_runtime_events_created_at"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_handled_at"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_user_id"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_request_id"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_status_code"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_path"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_event_type"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_level"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_id"), table_name="runtime_events")
    op.drop_table("runtime_events")

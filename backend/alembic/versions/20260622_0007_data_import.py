"""data import tracking table

Revision ID: 20260622_0007
Revises: 20260622_0006
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_0007"
down_revision: Union[str, None] = "20260622_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

import_source_type = sa.Enum("csv", "excel", "api", name="import_source_type")
import_status = sa.Enum("pending", "processing", "completed", "failed", name="import_status")


def upgrade() -> None:
    op.create_table(
        "data_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", import_source_type, nullable=False),
        sa.Column("status", import_status, nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_data_imports_id"), "data_imports", ["id"], unique=False)
    op.create_index(op.f("ix_data_imports_admin_id"), "data_imports", ["admin_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_data_imports_admin_id"), table_name="data_imports")
    op.drop_index(op.f("ix_data_imports_id"), table_name="data_imports")
    op.drop_table("data_imports")
    import_source_type.drop(op.get_bind(), checkfirst=True)
    import_status.drop(op.get_bind(), checkfirst=True)

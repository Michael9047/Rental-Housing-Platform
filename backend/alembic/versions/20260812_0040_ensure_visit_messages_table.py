"""ensure visit messages table

Revision ID: 20260812_0040
Revises: a56c94b83109
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_0040"
down_revision: Union[str, None] = "a56c94b83109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "apartment_visit_messages" not in inspector.get_table_names():
        op.create_table(
            "apartment_visit_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("apartment_id", sa.Integer(), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("guest_phone", sa.String(32), nullable=False),
            sa.Column("guest_message", sa.Text(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    indexes = {index["name"] for index in inspector.get_indexes("apartment_visit_messages")}
    if "ix_apartment_visit_messages_apartment_id" not in indexes:
        op.create_index(
            "ix_apartment_visit_messages_apartment_id",
            "apartment_visit_messages",
            ["apartment_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "apartment_visit_messages" in inspector.get_table_names():
        op.drop_table("apartment_visit_messages")

"""user_favorites table

Revision ID: 20260629_0009
Revises: 20260623_0008
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260629_0009"
down_revision: Union[str, None] = "20260623_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_favorites",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.BigInteger(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "property_id", name="uq_user_favorite_property"),
    )
    op.create_index("ix_user_favorites_user_id", "user_favorites", ["user_id"])
    op.create_index("ix_user_favorites_property_id", "user_favorites", ["property_id"])


def downgrade() -> None:
    op.drop_table("user_favorites")

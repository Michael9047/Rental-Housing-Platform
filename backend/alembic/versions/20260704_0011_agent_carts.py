"""agent carts and cart items

Revision ID: 20260704_0011
Revises: 5ac4aa5f38f4
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260704_0011"
down_revision: Union[str, None] = "5ac4aa5f38f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_carts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_agent_carts_id"), "agent_carts", ["id"], unique=False)
    op.create_index(op.f("ix_agent_carts_user_id"), "agent_carts", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_carts_session_id"), "agent_carts", ["session_id"], unique=False)

    op.create_table(
        "agent_cart_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cart_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cart_id"], ["agent_carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("cart_id", "property_id", name="uq_agent_cart_items_cart_property"),
    )
    op.create_index(op.f("ix_agent_cart_items_id"), "agent_cart_items", ["id"], unique=False)
    op.create_index(op.f("ix_agent_cart_items_cart_id"), "agent_cart_items", ["cart_id"], unique=False)
    op.create_index(op.f("ix_agent_cart_items_property_id"), "agent_cart_items", ["property_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_cart_items_property_id"), table_name="agent_cart_items")
    op.drop_index(op.f("ix_agent_cart_items_cart_id"), table_name="agent_cart_items")
    op.drop_index(op.f("ix_agent_cart_items_id"), table_name="agent_cart_items")
    op.drop_table("agent_cart_items")
    op.drop_index(op.f("ix_agent_carts_session_id"), table_name="agent_carts")
    op.drop_index(op.f("ix_agent_carts_user_id"), table_name="agent_carts")
    op.drop_index(op.f("ix_agent_carts_id"), table_name="agent_carts")
    op.drop_table("agent_carts")

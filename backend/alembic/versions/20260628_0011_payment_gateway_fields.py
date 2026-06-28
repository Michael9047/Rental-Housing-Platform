"""add payment gateway tracking fields

Revision ID: 20260628_0011
Revises: 20260626_0010
Create Date: 2026-06-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260628_0011"
down_revision: Union[str, None] = "20260626_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("out_trade_no", sa.String(length=64), nullable=True))
    op.add_column("payments", sa.Column("prepay_id", sa.String(length=128), nullable=True))
    op.add_column("payments", sa.Column("trade_state", sa.String(length=32), nullable=True))
    op.add_column("payments", sa.Column("trade_state_desc", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_payments_out_trade_no"), "payments", ["out_trade_no"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_payments_out_trade_no"), table_name="payments")
    op.drop_column("payments", "trade_state_desc")
    op.drop_column("payments", "trade_state")
    op.drop_column("payments", "prepay_id")
    op.drop_column("payments", "out_trade_no")

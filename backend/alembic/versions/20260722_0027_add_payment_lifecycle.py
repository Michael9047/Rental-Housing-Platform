"""增加订单支付生命周期和库存预留标记。

Revision ID: 20260722_0027
Revises: 20260722_0026
"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_0027"
down_revision = "20260722_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("payment_processing", "paid", "payment_failed", "payment_expired", "refund_pending", "refunded", "payment_review"):
        op.execute(f"ALTER TYPE booking_status ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("expired", "review", "refund_pending", "refunded"):
        op.execute(f"ALTER TYPE payment_status ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column("bookings", sa.Column("inventory_reserved", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    # PostgreSQL 枚举值不可安全原地删除，仅回滚新增列。
    op.drop_column("bookings", "inventory_reserved")

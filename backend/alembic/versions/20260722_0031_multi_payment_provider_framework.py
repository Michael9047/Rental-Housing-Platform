"""增加不可变支付订单号和支付尝试号。"""

from alembic import op
import sqlalchemy as sa

revision = "20260722_0031"
down_revision = "20260722_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("order_id", sa.String(length=64), nullable=True))
    op.add_column("payments", sa.Column("payment_attempt_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE payments SET order_id = 'PAY-' || upper(replace(id, '-', '')), payment_attempt_id = id WHERE order_id IS NULL")
    op.alter_column("payments", "order_id", nullable=False)
    op.alter_column("payments", "payment_attempt_id", nullable=False)
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=True)
    op.create_index("ix_payments_payment_attempt_id", "payments", ["payment_attempt_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_payments_payment_attempt_id", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_column("payments", "payment_attempt_id")
    op.drop_column("payments", "order_id")

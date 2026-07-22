"""补齐支付交易字段并统一支付状态枚举

Revision ID: 20260722_0019
Revises: 20260722_0018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260722_0019"
down_revision: Union[str, None] = "20260722_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("out_trade_no", sa.String(255), nullable=True))
    op.add_column("payments", sa.Column("trade_state", sa.String(50), nullable=True))
    op.add_column("payments", sa.Column("trade_state_desc", sa.String(255), nullable=True))
    op.execute(
        "CREATE TYPE payment_status AS ENUM "
        "('pending','processing','success','failed','closed')"
    )
    op.execute("ALTER TABLE payments ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE payments ALTER COLUMN status TYPE payment_status "
        "USING status::text::payment_status"
    )
    op.execute("ALTER TABLE payments ALTER COLUMN status SET DEFAULT 'pending'::payment_status")
    op.create_index("ux_payments_out_trade_no", "payments", ["out_trade_no"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_payments_out_trade_no", table_name="payments")
    op.execute("ALTER TABLE payments ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE payments ALTER COLUMN status TYPE varchar(20) USING status::text")
    op.execute("ALTER TABLE payments ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("DROP TYPE payment_status")
    op.drop_column("payments", "trade_state_desc")
    op.drop_column("payments", "trade_state")
    op.drop_column("payments", "out_trade_no")

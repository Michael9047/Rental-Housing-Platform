"""补齐支付、合同与认证通知类型

Revision ID: 20260722_0020
Revises: 20260722_0019
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260722_0020"
down_revision: Union[str, None] = "20260722_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in (
        "payment_created",
        "payment_failed",
        "payment_expired",
        "contract_generated",
        "contract_signed",
        "auth_registration",
        "auth_password_reset",
    ):
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL 不支持安全删除单个枚举值；降级保留兼容值。
    pass

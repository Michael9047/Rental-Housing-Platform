"""新建 apartment_visit_messages 预约看房消息表"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260731_0039"
down_revision: Union[str, None] = "20260730_0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "apartment_visit_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("apartment_id", sa.Integer(), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("guest_phone", sa.String(32), nullable=False),
        sa.Column("guest_message", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("apartment_visit_messages")

"""增加房东预订成功通知所需的邮箱验证和投递审计字段。"""

from alembic import op
import sqlalchemy as sa

revision = "20260722_0030"
down_revision = "20260722_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 部分开发库曾由旧版本 create_all 提前创建该列，因此迁移需保持幂等。
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false")
    op.add_column("notification_outbox", sa.Column("recipient_email", sa.String(length=255), nullable=True))
    op.add_column("notification_outbox", sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_outbox", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification_outbox", sa.Column("provider_message_id", sa.String(length=255), nullable=True))
    op.execute("UPDATE notification_outbox SET queued_at = created_at WHERE queued_at IS NULL")
    op.alter_column("notification_outbox", "queued_at", nullable=False)
    op.alter_column("users", "email_verified", server_default=None)
    op.alter_column("notification_outbox", "retryable", server_default=None)


def downgrade() -> None:
    op.drop_column("notification_outbox", "provider_message_id")
    op.drop_column("notification_outbox", "queued_at")
    op.drop_column("notification_outbox", "retryable")
    op.drop_column("notification_outbox", "recipient_email")
    op.drop_column("users", "email_verified")

"""增加事务型消息通知 outbox。

Revision ID: 20260722_0028
Revises: 20260722_0027
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20260722_0028"; down_revision="20260722_0027"; branch_labels=None; depends_on=None

def upgrade() -> None:
    status=postgresql.ENUM("pending","processing","sent","failed",name="notification_outbox_status",create_type=False)
    status.create(op.get_bind(), checkfirst=True)
    op.create_table("notification_outbox", sa.Column("id",sa.String(36),primary_key=True),sa.Column("event_key",sa.String(180),nullable=False,unique=True),sa.Column("event_type",sa.String(60),nullable=False),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("booking_id",sa.Integer(),sa.ForeignKey("bookings.id",ondelete="CASCADE")),sa.Column("channel",sa.String(20),nullable=False,server_default="email"),sa.Column("template_version",sa.String(20),nullable=False),sa.Column("payload",postgresql.JSONB(),nullable=False),sa.Column("status",status,nullable=False,server_default="pending"),sa.Column("attempts",sa.Integer(),nullable=False,server_default="0"),sa.Column("last_error",sa.String(500)),sa.Column("next_attempt_at",sa.DateTime(timezone=True)),sa.Column("sent_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    for name in ("event_key","event_type","user_id","booking_id","status","next_attempt_at"): op.create_index(f"ix_notification_outbox_{name}","notification_outbox",[name])

def downgrade() -> None:
    op.drop_table("notification_outbox"); postgresql.ENUM(name="notification_outbox_status").drop(op.get_bind(),checkfirst=True)

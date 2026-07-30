"""为站内通知增加结构化业务关联字段。"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_0032"
down_revision = "20260722_0031"
branch_labels = None
depends_on = None

def upgrade() -> None:
    for name, typ in [("body", sa.Text()), ("entity_type", sa.String(40)), ("entity_id", sa.String(100)), ("order_id", sa.String(64)), ("agreement_id", sa.String(100)), ("property_id", sa.Integer())]:
        op.add_column("notifications", sa.Column(name, typ, nullable=True))
    op.create_index("ix_notifications_user_read_created", "notifications", ["user_id", "is_read", "created_at"])
    op.create_index("ix_notifications_user_entity", "notifications", ["user_id", "entity_type", "entity_id"])
    op.execute("UPDATE notifications SET body = content WHERE body IS NULL")

def downgrade() -> None:
    op.drop_index("ix_notifications_user_entity", table_name="notifications")
    op.drop_index("ix_notifications_user_read_created", table_name="notifications")
    for name in ["property_id", "agreement_id", "order_id", "entity_id", "entity_type", "body"]:
        op.drop_column("notifications", name)

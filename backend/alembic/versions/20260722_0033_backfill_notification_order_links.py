"""仅安全回填能唯一确认归属的历史订单通知。"""
from alembic import op

revision = "20260722_0033"
down_revision = "20260722_0032"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 历史正文中的订单号仅用于一次性、受 tenant_id 约束的迁移；前端从不解析正文。
    op.execute("""
        WITH candidates AS (
          SELECT n.id AS notification_id, b.id AS booking_id, b.property_id,
                 (SELECT p.order_id FROM payments p WHERE p.booking_id = b.id ORDER BY p.created_at DESC LIMIT 1) AS payment_order_id,
                 (SELECT c.id FROM contracts c WHERE c.booking_id = b.id ORDER BY c.version DESC LIMIT 1) AS contract_id
          FROM notifications n
          JOIN LATERAL regexp_match(COALESCE(n.content, ''), '订单 #[[:space:]]*([0-9]+)') m ON true
          JOIN bookings b ON b.id = (m[1])::integer AND b.tenant_id = n.user_id
          WHERE n.entity_id IS NULL
        )
        UPDATE notifications n SET entity_type = 'order', entity_id = c.booking_id::text,
          order_id = COALESCE(c.payment_order_id, c.booking_id::text), property_id = c.property_id,
          agreement_id = c.contract_id::text
        FROM candidates c WHERE n.id = c.notification_id
    """)

def downgrade() -> None:
    # 回滚不删除既有通知，仅清理本迁移写入的结构化链接。
    op.execute("UPDATE notifications SET entity_type = NULL, entity_id = NULL, order_id = NULL, property_id = NULL, agreement_id = NULL WHERE entity_type = 'order'")

"""按有效订单校准户型库存。

Revision ID: 20260813_0047
Revises: 20260813_0046
Create Date: 2026-08-13
"""

from alembic import op


revision = "20260813_0047"
down_revision = "20260813_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用总套数减去有效订单数，修复历史剩余库存。"""
    op.execute(
        """
        WITH occupied AS (
            SELECT unit_type_id, COUNT(*) AS occupied_count
            FROM bookings
            WHERE status IN (
                'contract_signed',
                'payment_pending',
                'payment_processing',
                'paid',
                'completed'
            )
              AND unit_type_id IS NOT NULL
            GROUP BY unit_type_id
        )
        UPDATE unit_types AS unit_type
        SET available_count = GREATEST(
                0,
                unit_type.total_count - COALESCE(occupied.occupied_count, 0)
            ),
            has_vacancy = unit_type.total_count - COALESCE(occupied.occupied_count, 0) > 0
        FROM occupied
        WHERE occupied.unit_type_id = unit_type.id
        """
    )


def downgrade() -> None:
    """旧库存值无法可靠还原，降级时保留已校准数据。"""
    pass

"""回填历史公寓的 BM 归属。

Revision ID: 20260813_0046
Revises: 20260813_0045
Create Date: 2026-08-13
"""

from alembic import op


revision = "20260813_0046"
down_revision = "20260813_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """仅把由 BM 创建且尚未分配的公寓回填给创建者。"""
    op.execute(
        """
        UPDATE institutes AS institute
        SET bm_id = institute.created_by
        FROM users AS creator
        WHERE institute.bm_id IS NULL
          AND creator.id = institute.created_by
          AND creator.role = 'landlord'
        """
    )


def downgrade() -> None:
    """归属数据可能已被人工确认，降级时不做破坏性清空。"""
    pass

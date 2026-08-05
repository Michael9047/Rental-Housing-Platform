"""rename repair_requests landlord→bm and add missing enum values

Revision ID: 20260804_rename_bm
Revises: 8c314438f8b1
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260804_rename_bm'
down_revision: Union[str, None] = '8c314438f8b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加模型中有但枚举中没有的值
    op.execute("ALTER TYPE repair_status ADD VALUE IF NOT EXISTS 'confirmed'")
    op.execute("ALTER TYPE repair_status ADD VALUE IF NOT EXISTS 'pending_escalated'")

    # 2. 重命名 landlord_id → bm_id（unit_type_id 已由之前的迁移手动完成）
    op.execute("DROP INDEX IF EXISTS ix_repair_requests_landlord_id")
    op.execute("ALTER TABLE repair_requests DROP CONSTRAINT IF EXISTS repair_requests_landlord_id_fkey")
    op.execute("ALTER TABLE repair_requests RENAME COLUMN landlord_id TO bm_id")
    op.execute(
        "ALTER TABLE repair_requests ADD CONSTRAINT repair_requests_bm_id_fkey "
        "FOREIGN KEY (bm_id) REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_repair_requests_bm_id ON repair_requests (bm_id)")


def downgrade() -> None:
    # 索引 + 外键
    op.execute("DROP INDEX IF EXISTS ix_repair_requests_bm_id")
    op.execute("ALTER TABLE repair_requests DROP CONSTRAINT IF EXISTS repair_requests_bm_id_fkey")

    # 列名回退
    op.execute("ALTER TABLE repair_requests RENAME COLUMN bm_id TO landlord_id")

    op.execute(
        "ALTER TABLE repair_requests ADD CONSTRAINT repair_requests_landlord_id_fkey "
        "FOREIGN KEY (landlord_id) REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_repair_requests_landlord_id ON repair_requests (landlord_id)")

"""增加公寓与户型主动下架状态。

Revision ID: 20260813_0043
Revises: 20260813_0042
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260813_0043"
down_revision: Union[str, None] = "20260813_0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE institute_status ADD VALUE IF NOT EXISTS 'offline'")
    op.execute("ALTER TYPE room_type_status ADD VALUE IF NOT EXISTS 'offline'")


def downgrade() -> None:
    # PostgreSQL 不支持直接删除枚举值，回滚时重建枚举并恢复列默认值。
    op.execute("ALTER TABLE institutes ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE unit_types ALTER COLUMN status DROP DEFAULT")
    op.execute("UPDATE institutes SET status = 'suspended' WHERE status::text = 'offline'")
    op.execute("UPDATE unit_types SET status = 'maintenance' WHERE status::text = 'offline'")
    op.execute("ALTER TYPE institute_status RENAME TO institute_status_with_offline")
    op.execute("CREATE TYPE institute_status AS ENUM ('pending', 'active', 'suspended')")
    op.execute(
        "ALTER TABLE institutes ALTER COLUMN status TYPE institute_status "
        "USING status::text::institute_status"
    )
    op.execute("DROP TYPE institute_status_with_offline")
    op.execute("ALTER TYPE room_type_status RENAME TO room_type_status_with_offline")
    op.execute("CREATE TYPE room_type_status AS ENUM ('available', 'rented', 'maintenance')")
    op.execute(
        "ALTER TABLE unit_types ALTER COLUMN status TYPE room_type_status "
        "USING status::text::room_type_status"
    )
    op.execute("DROP TYPE room_type_status_with_offline")
    op.execute("ALTER TABLE institutes ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("ALTER TABLE unit_types ALTER COLUMN status SET DEFAULT 'available'")

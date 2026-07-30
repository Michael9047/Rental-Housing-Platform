"""修复 status 列类型：varchar → 正确的 PostgreSQL ENUM

rooms.status       → property_status enum（补 pending_review 值）
unit_types.status  → unit_type_status enum
"""

from typing import Sequence, Union
from alembic import op

revision: str = "20260726_0034"
down_revision: Union[str, None] = "e5f6a7b8c9d0"  # special_discount_to_text
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 补 property_status 枚举的 pending_review 值 ──
    op.execute("ALTER TYPE property_status ADD VALUE IF NOT EXISTS 'pending_review'")

    # ── 2. rooms.status → property_status ──
    op.execute("ALTER TABLE rooms ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE rooms ALTER COLUMN status TYPE property_status "
        "USING status::text::property_status"
    )
    op.execute(
        "ALTER TABLE rooms ALTER COLUMN status "
        "SET DEFAULT 'available'::property_status"
    )

    # ── 3. unit_types.status → unit_type_status ──
    op.execute("ALTER TABLE unit_types ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE unit_types ALTER COLUMN status TYPE unit_type_status "
        "USING status::text::unit_type_status"
    )
    op.execute(
        "ALTER TABLE unit_types ALTER COLUMN status "
        "SET DEFAULT 'available'::unit_type_status"
    )


def downgrade() -> None:
    # ── rooms.status → varchar ──
    op.execute("ALTER TABLE rooms ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE rooms ALTER COLUMN status TYPE VARCHAR(50) "
        "USING status::VARCHAR"
    )
    op.execute(
        "ALTER TABLE rooms ALTER COLUMN status "
        "SET DEFAULT 'available'::VARCHAR"
    )

    # ── unit_types.status → varchar ──
    op.execute("ALTER TABLE unit_types ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE unit_types ALTER COLUMN status TYPE VARCHAR(50) "
        "USING status::VARCHAR"
    )
    op.execute(
        "ALTER TABLE unit_types ALTER COLUMN status "
        "SET DEFAULT 'available'::VARCHAR"
    )

    # NOTE: 不回滚 property_status 枚举的 pending_review 值
    # （PostgreSQL 不支持从 enum 中删除值）

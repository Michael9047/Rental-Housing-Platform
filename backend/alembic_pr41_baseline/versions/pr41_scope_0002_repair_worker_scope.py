"""将 PR41 维修师傅范围字段统一为 worker_scope 枚举。

Revision ID: pr41_scope_0002
Revises: 18a763bb049c
Create Date: 2026-08-05 11:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pr41_scope_0002"
down_revision: Union[str, None] = "18a763bb049c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """幂等补齐 enum、列类型、默认值和非空约束。"""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'worker_scope') THEN
                CREATE TYPE worker_scope AS ENUM ('platform', 'apartment');
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            scope_type TEXT;
        BEGIN
            IF to_regclass('public.repair_workers') IS NULL THEN
                RETURN;
            END IF;

            SELECT udt_name INTO scope_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'repair_workers'
              AND column_name = 'scope';

            IF scope_type IS NULL THEN
                ALTER TABLE repair_workers
                    ADD COLUMN scope worker_scope NOT NULL DEFAULT 'apartment';
            ELSIF scope_type <> 'worker_scope' THEN
                ALTER TABLE repair_workers ALTER COLUMN scope DROP DEFAULT;
                UPDATE repair_workers
                SET scope = 'apartment'
                WHERE scope IS NULL OR scope::TEXT NOT IN ('platform', 'apartment');
                ALTER TABLE repair_workers
                    ALTER COLUMN scope TYPE worker_scope
                    USING scope::TEXT::worker_scope;
                ALTER TABLE repair_workers
                    ALTER COLUMN scope SET DEFAULT 'apartment';
                ALTER TABLE repair_workers ALTER COLUMN scope SET NOT NULL;
            ELSE
                UPDATE repair_workers SET scope = 'apartment' WHERE scope IS NULL;
                ALTER TABLE repair_workers
                    ALTER COLUMN scope SET DEFAULT 'apartment';
                ALTER TABLE repair_workers ALTER COLUMN scope SET NOT NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """本地兼容修复不回退，避免破坏已有维修人员数据。"""
    pass

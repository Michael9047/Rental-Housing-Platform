"""PR1: Institute + UnitType 扩充字段，清空房源数据为重新填充做准备

Revision ID: 20260730_pr1
Revises: 983b708fb08f
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260730_pr1"
down_revision = "983b708fb08f"
branch_labels = None
depends_on = None


# ── 辅助函数：安全 DDL，兼容各环境 schema 差异 ──

def _column_exists(table: str, column: str) -> bool:
    """检查列是否已存在"""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": "public", "table": table, "column": column},
    )
    return result.fetchone() is not None


def _index_exists(index_name: str) -> bool:
    """检查索引是否已存在"""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'public' AND indexname = :name"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def _add_column_if_not_exists(table: str, column: sa.Column) -> None:
    """仅在列不存在时添加"""
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def _create_index_if_not_exists(index_name: str, table: str, columns: list[str]) -> None:
    """仅在索引不存在时创建"""
    if not _index_exists(index_name):
        op.create_index(index_name, table, columns)


def upgrade():
    # ── Step 1: 清空所有房源相关数据 ──
    # 动态检测表是否存在再删除，兼容各环境 schema 差异
    op.execute("""
        DO $$
        DECLARE
            tbl TEXT;
        BEGIN
            FOREACH tbl IN ARRAY ARRAY[
                -- 叶子表（按 FK 依赖反序）
                'contract_signatures', 'payments', 'audit_logs', 'embedding_jobs',
                'agent_cart_items', 'user_favorites', 'booking_flow_drafts',
                'reviews', 'contracts', 'repair_requests', 'bookings', 'orders',
                'notifications', 'room_transfers', 'room_images', 'room_commutes',
                'compare_sessions', 'property_pois', 'property_images',
                -- 主表
                'rooms', 'properties', 'unit_types', 'building_images', 'building_staff',
                'institutes'
            ] LOOP
                IF EXISTS (SELECT 1 FROM information_schema.tables
                           WHERE table_schema = 'public' AND table_name = tbl) THEN
                    EXECUTE 'DELETE FROM ' || quote_ident(tbl);
                END IF;
            END LOOP;
        END $$;
    """)

    # ── Step 2: Institute 新增字段（安全添加，跳过已存在的列） ──
    _add_column_if_not_exists("institutes", sa.Column("building_type", sa.String(50), nullable=True))
    _add_column_if_not_exists("institutes", sa.Column("total_floors", sa.Integer(), nullable=True))
    _add_column_if_not_exists("institutes", sa.Column("year_built", sa.Integer(), nullable=True))
    _add_column_if_not_exists("institutes", sa.Column("total_units", sa.Integer(), nullable=True))
    _add_column_if_not_exists("institutes", sa.Column("has_elevator", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # BM（商务经理）归属 + 联系方式
    _add_column_if_not_exists("institutes", sa.Column("bm_id", sa.Integer(),
                              sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    _create_index_if_not_exists("ix_institutes_bm_id", "institutes", ["bm_id"])
    _add_column_if_not_exists("institutes", sa.Column("bm_wechat", sa.String(100), nullable=True))
    _add_column_if_not_exists("institutes", sa.Column("bm_wechat_qr", sa.String(500), nullable=True))

    # 其他
    _add_column_if_not_exists("institutes", sa.Column("website_url", sa.String(500), nullable=True))

    # ── Step 3: UnitType 新增字段（安全添加，跳过已存在的列） ──
    _add_column_if_not_exists("unit_types", sa.Column("property_type", sa.String(50), nullable=True))
    _add_column_if_not_exists("unit_types", sa.Column("total_count", sa.Integer(), nullable=False,
                              server_default=sa.text("1")))
    _add_column_if_not_exists("unit_types", sa.Column("available_count", sa.Integer(), nullable=False,
                              server_default=sa.text("1")))
    _add_column_if_not_exists("unit_types", sa.Column("has_vacancy", sa.Boolean(), nullable=False,
                              server_default=sa.text("true")))


def downgrade():
    # ── UnitType 回滚 ──
    _drop_column_if_exists("unit_types", "has_vacancy")
    _drop_column_if_exists("unit_types", "available_count")
    _drop_column_if_exists("unit_types", "total_count")
    _drop_column_if_exists("unit_types", "property_type")

    # ── Institute 回滚 ──
    _drop_column_if_exists("institutes", "website_url")
    _drop_column_if_exists("institutes", "bm_wechat_qr")
    _drop_column_if_exists("institutes", "bm_wechat")
    _drop_index_if_exists("ix_institutes_bm_id", table_name="institutes")
    _drop_column_if_exists("institutes", "bm_id")
    _drop_column_if_exists("institutes", "has_elevator")
    _drop_column_if_exists("institutes", "total_units")
    _drop_column_if_exists("institutes", "year_built")
    _drop_column_if_exists("institutes", "total_floors")
    _drop_column_if_exists("institutes", "building_type")

    # 数据已删除，downgrade 无法恢复


def _drop_column_if_exists(table: str, column: str) -> None:
    """仅在列存在时删除"""
    if _column_exists(table, column):
        op.drop_column(table, column)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    """仅在索引存在时删除"""
    if _index_exists(index_name):
        op.drop_index(index_name, table_name=table_name)

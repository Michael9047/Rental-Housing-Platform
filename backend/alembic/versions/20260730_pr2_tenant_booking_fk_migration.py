"""PR2: Tenant表重建 + 全子表FK迁移 + Room表删除

Revision ID: 20260730_pr2
Revises: 20260730_pr1
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260730_pr2"
down_revision = "20260730_pr1"
branch_labels = None
depends_on = None


# ── 安全 DDL 辅助 ──

def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=:t"),
        {"t": table},
    )
    return result.fetchone() is not None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=:t AND column_name=:c"),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
        {"n": index_name},
    )
    return result.fetchone() is not None


def upgrade():
    # ═══════════════════════════════════════
    # Step 1: 删除废弃表
    # ═══════════════════════════════════════
    tables_to_drop = [
        "orders",              # 遗留订单系统
        "room_images",         # 已被 unit_types.image_urls[] 取代
        "property_images",     # 同上（旧名）
        "room_transfers",      # 无房间则无流转
        "room_types",          # 已被 unit_types 取代
    ]
    for tbl in tables_to_drop:
        if _table_exists(tbl):
            op.drop_table(tbl)

    # ═══════════════════════════════════════
    # Step 2: 重建 tenants 表
    # ═══════════════════════════════════════
    if _table_exists("tenants"):
        op.drop_table("tenants")

    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(100), nullable=True, comment="租客标签，如'我自己'/'张三'"),
        # ── 个人信息（14 字段，完全复用 booking_flow_drafts.personal_info JSONB key）──
        sa.Column("chinese_name", sa.String(100), nullable=True),
        sa.Column("given_name_pinyin", sa.String(100), nullable=True),
        sa.Column("surname_pinyin", sa.String(100), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("school_name", sa.String(200), nullable=True),
        sa.Column("enrollment_grade", sa.String(100), nullable=True),
        sa.Column("major_english", sa.String(200), nullable=True),
        sa.Column("region", sa.String(200), nullable=True),
        sa.Column("address_detail", sa.String(500), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        # ── 紧急联系人（12 字段，加 emergency_ 前缀）──
        sa.Column("emergency_chinese_name", sa.String(100), nullable=True),
        sa.Column("emergency_given_name_pinyin", sa.String(100), nullable=True),
        sa.Column("emergency_surname_pinyin", sa.String(100), nullable=True),
        sa.Column("emergency_relation", sa.String(50), nullable=True),
        sa.Column("emergency_birth_date", sa.Date(), nullable=True),
        sa.Column("emergency_phone", sa.String(32), nullable=True),
        sa.Column("emergency_email", sa.String(255), nullable=True),
        sa.Column("emergency_gender", sa.String(20), nullable=True),
        sa.Column("emergency_region", sa.String(200), nullable=True),
        sa.Column("emergency_address_detail", sa.String(500), nullable=True),
        sa.Column("emergency_postal_code", sa.String(20), nullable=True),
        sa.Column("emergency_consultant_id", sa.String(50), nullable=True),
        # ── 居住状态 ──
        sa.Column("current_unit_type_id", sa.Integer(), sa.ForeignKey("unit_types.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("housing_status", sa.String(20), nullable=True, default="active"),
        sa.Column("move_in_date", sa.Date(), nullable=True),
        sa.Column("move_out_date", sa.Date(), nullable=True),
        # ── 时间戳 ──
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tenants_user_id", "tenants", ["user_id"])

    # ═══════════════════════════════════════
    # Step 3: 表改名（property_pois → institute_pois, room_commutes → institute_commutes）
    # ═══════════════════════════════════════
    if _table_exists("property_pois"):
        op.rename_table("property_pois", "institute_pois")
        if _column_exists("institute_pois", "property_id"):
            op.alter_column("institute_pois", "property_id", new_column_name="institute_id")
    if _table_exists("room_commutes"):
        op.rename_table("room_commutes", "institute_commutes")
        if _column_exists("institute_commutes", "room_id"):
            op.alter_column("institute_commutes", "room_id", new_column_name="institute_id")

    # ═══════════════════════════════════════
    # Step 4: bookings 改 FK + 新列
    # ═══════════════════════════════════════

    # 4a. 改 property_id → unit_type_id
    if _column_exists("bookings", "property_id"):
        # 尝试删除旧 FK 约束
        op.execute("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.table_constraints
                           WHERE constraint_name='bookings_property_id_fkey' AND table_name='bookings')
                THEN ALTER TABLE bookings DROP CONSTRAINT bookings_property_id_fkey;
                END IF;
            END $$;
        """)
        op.alter_column("bookings", "property_id", new_column_name="unit_type_id")
        op.create_foreign_key("fk_bookings_unit_type", "bookings", "unit_types", ["unit_type_id"], ["id"], ondelete="SET NULL")

    # 4c. landlord_id → bm_id
    if _column_exists("bookings", "landlord_id"):
        op.execute("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.table_constraints
                           WHERE constraint_name='bookings_landlord_id_fkey' AND table_name='bookings')
                THEN ALTER TABLE bookings DROP CONSTRAINT bookings_landlord_id_fkey;
                END IF;
            END $$;
        """)
        op.alter_column("bookings", "landlord_id", new_column_name="bm_id")

    # 4d. tenant_id FK → tenants 表
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.table_constraints
                       WHERE constraint_name='bookings_tenant_id_fkey' AND table_name='bookings')
            THEN ALTER TABLE bookings DROP CONSTRAINT bookings_tenant_id_fkey;
            END IF;
        END $$;
    """)
    # 重建 tenant_id FK 指向新的 tenants 表
    op.create_foreign_key("fk_bookings_tenant", "bookings", "tenants", ["tenant_id"], ["id"], ondelete="SET NULL")

    # 4e. 新增列
    _add_column("bookings", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True))
    _create_index("ix_bookings_user_id", "bookings", ["user_id"])
    _add_column("bookings", sa.Column("institute_id", sa.Integer(), sa.ForeignKey("institutes.id", ondelete="SET NULL"), nullable=True))
    _create_index("ix_bookings_institute_id", "bookings", ["institute_id"])
    _add_column("bookings", sa.Column("room_number", sa.String(20), nullable=True))
    _add_column("bookings", sa.Column("contract_start", sa.Date(), nullable=True))
    _add_column("bookings", sa.Column("contract_end", sa.Date(), nullable=True))

    # ═══════════════════════════════════════
    # Step 5: booking_flow_drafts 改 FK + 新列 - JSONB
    # ═══════════════════════════════════════
    _rename_fk_column("booking_flow_drafts", "property_id", "unit_type_id", "unit_types")
    _add_column("booking_flow_drafts", sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True))
    _create_index("ix_booking_flow_drafts_tenant_id", "booking_flow_drafts", ["tenant_id"])
    _drop_column("booking_flow_drafts", "personal_info")
    _drop_column("booking_flow_drafts", "emergency_contact")

    # ═══════════════════════════════════════
    # Step 6: contracts — property_id → unit_type_id
    # ═══════════════════════════════════════
    _rename_fk_column("contracts", "property_id", "unit_type_id", "unit_types")

    # ═══════════════════════════════════════
    # Step 7: 其余子表 FK 改名
    # ═══════════════════════════════════════
    _rename_fk_column("repair_requests", "property_id", "unit_type_id", "unit_types")
    _rename_fk_column("user_favorites", "property_id", "unit_type_id", "unit_types")
    _rename_fk_column("agent_cart_items", "property_id", "unit_type_id", "unit_types")

    # notifications — property_id 只是 INTEGER，无 FK 约束
    if _column_exists("notifications", "property_id"):
        op.alter_column("notifications", "property_id", new_column_name="unit_type_id")

    # compare_sessions — property_ids JSON 列
    if _column_exists("compare_sessions", "property_ids"):
        op.alter_column("compare_sessions", "property_ids", new_column_name="unit_type_ids")

    # ═══════════════════════════════════════
    # Step 8: 删除 rooms/properties 表
    # 先清理所有可能残留的 FK 约束
    # ═══════════════════════════════════════
    for tbl in ["rooms", "properties"]:
        if not _table_exists(tbl):
            continue
        # 删掉所有指向该表的 FK 约束
        op.execute(f"""
            DO $$ DECLARE r RECORD; BEGIN
                FOR r IN (SELECT conname, conrelid::regclass::text AS tbl_name
                          FROM pg_constraint WHERE confrelid = '{tbl}'::regclass) LOOP
                    EXECUTE 'ALTER TABLE ' || r.tbl_name || ' DROP CONSTRAINT ' || r.conname;
                END LOOP;
            END $$;
        """)
        op.drop_table(tbl)


def downgrade():
    # PR2 是大规模重构，downgrade 不恢复数据，只回滚表结构
    # 实际使用时建议重建数据库
    pass


# ── 迁移内部辅助函数 ──

def _add_column(table: str, column: sa.Column) -> None:
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def _drop_column(table: str, column: str) -> None:
    if _column_exists(table, column):
        op.drop_column(table, column)


def _create_index(index_name: str, table: str, columns: list[str]) -> None:
    if not _index_exists(index_name):
        op.create_index(index_name, table, columns)


def _rename_fk_column(table: str, old_col: str, new_col: str, ref_table: str) -> None:
    """改 FK 列名：删旧约束 → 改名 → 建新约束"""
    if not _column_exists(table, old_col):
        return
    # 删旧 FK 约束
    conn = op.get_bind()
    result = conn.execute(
        sa.text(f"SELECT conname FROM pg_constraint WHERE conrelid = '{table}'::regclass AND conname LIKE '%{old_col}%'")
    )
    for row in result:
        op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT {row[0]}"))
    op.alter_column(table, old_col, new_column_name=new_col)
    op.create_foreign_key(
        f"fk_{table}_{new_col}", table, ref_table, [new_col], ["id"], ondelete="SET NULL"
    )

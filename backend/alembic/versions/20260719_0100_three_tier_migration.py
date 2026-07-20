"""三层架构迁移：清空旧数据 + 重构表结构

公寓(institutes)增强 + 户型(unit_types) + 房间(rooms) + 配套表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20260719_0100'
down_revision: Union[str, None] = '20260719_0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══════════════════════════════════════════
    # 1. 清空旧数据
    # ═══════════════════════════════════════════
    op.execute("DELETE FROM agent_cart_items")
    op.execute("DELETE FROM user_favorites")
    op.execute("DELETE FROM property_images")
    op.execute("DELETE FROM property_pois")
    op.execute("DELETE FROM bookings")
    op.execute("DELETE FROM contracts")
    op.execute("DELETE FROM payments")
    op.execute("DELETE FROM reviews")
    op.execute("DELETE FROM compare_messages")
    op.execute("DELETE FROM compare_sessions")
    op.execute("DELETE FROM audit_logs")
    op.execute("DELETE FROM room_types")
    op.execute("DELETE FROM properties")

    # ═══════════════════════════════════════════
    # 2. institutes → 增强为公寓
    # ═══════════════════════════════════════════
    op.add_column('institutes', sa.Column('business_id', sa.String(20), nullable=True))
    op.create_index('ix_institutes_business_id', 'institutes', ['business_id'], unique=True)
    # 为现有公寓生成业务编号
    op.execute("UPDATE institutes SET business_id = 'APT-' || LPAD(id::text, 5, '0')")

    # ═══════════════════════════════════════════
    # 3. room_types → 重构为 unit_types
    # ═══════════════════════════════════════════
    # 删除旧约束
    op.execute("ALTER TABLE room_types DROP CONSTRAINT IF EXISTS room_types_property_id_fkey")
    op.drop_column('room_types', 'property_id')
    op.drop_column('room_types', 'price_monthly')
    op.drop_column('room_types', 'available_count')
    op.drop_column('room_types', 'floor')
    # 删除旧枚举 (先删列再删类型)
    op.execute("DROP TYPE IF EXISTS room_type_enum CASCADE")
    # 新增列
    op.add_column('room_types', sa.Column('institute_id', sa.Integer(), nullable=False))
    op.create_foreign_key('fk_unit_types_institute', 'room_types', 'institutes', ['institute_id'], ['id'], ondelete='CASCADE')
    op.add_column('room_types', sa.Column('hall_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('room_types', sa.Column('base_rent', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('room_types', sa.Column('floor_pricing', postgresql.JSONB(), nullable=True))
    # 重命名表
    op.rename_table('room_types', 'unit_types')
    # 索引
    op.create_index('ix_unit_types_institute_id', 'unit_types', ['institute_id'])

    # ═══════════════════════════════════════════
    # 4. properties → 重构为 rooms
    # ═══════════════════════════════════════════
    # 删除户型级字段
    drop_columns = [
        'title', 'description', 'address', 'district', 'price_monthly',
        'area_sqm', 'bedrooms', 'bathrooms', 'deposit_amount', 'deposit_type',
        'service_fee_rate', 'amenities', 'latitude', 'longitude',
        'rent_type', 'min_lease_months', 'max_lease_months',
        'embedding', 'rental_rules', 'country',
    ]
    for col in drop_columns:
        op.drop_column('properties', col)
    # 删除旧约束和FK
    op.execute("ALTER TABLE properties DROP CONSTRAINT IF EXISTS properties_institute_id_fkey")
    op.drop_column('properties', 'institute_id')
    op.drop_column('properties', 'room_number')
    op.execute("DROP TYPE IF EXISTS property_type CASCADE")
    op.execute("DROP TYPE IF EXISTS rent_type CASCADE")
    # 新增列
    op.add_column('properties', sa.Column('unit_type_id', sa.Integer(), nullable=False))
    op.create_foreign_key('fk_rooms_unit_type', 'properties', 'unit_types', ['unit_type_id'], ['id'], ondelete='CASCADE')
    op.add_column('properties', sa.Column('special_discount', sa.Numeric(12, 2), nullable=True))
    op.create_index('ix_rooms_unit_type_id', 'properties', ['unit_type_id'])
    # 重命名表
    op.rename_table('properties', 'rooms')
    # 重命名关联表
    op.rename_table('property_images', 'room_images')
    op.execute("ALTER TABLE room_images RENAME COLUMN property_id TO room_id")

    # ═══════════════════════════════════════════
    # 5. 新建 building_staff 表
    # ═══════════════════════════════════════════
    op.create_table('building_staff',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('institute_id', sa.Integer(), sa.ForeignKey('institutes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='staff'),
        sa.Column('phone', sa.String(32), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # ═══════════════════════════════════════════
    # 6. 新建 room_transfers 表
    # ═══════════════════════════════════════════
    op.create_table('room_transfers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('room_id', sa.Integer(), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('from_status', sa.String(30), nullable=True),
        sa.Column('to_status', sa.String(30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('operator_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # ═══════════════════════════════════════════
    # 7. 新建 tenants 表
    # ═══════════════════════════════════════════
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('phone', sa.String(32), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('id_number', sa.String(50), nullable=True),
        sa.Column('emergency_contact', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # ═══════════════════════════════════════════
    # 8. 新建 orders 表
    # ═══════════════════════════════════════════
    op.create_table('orders',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('room_id', sa.Integer(), sa.ForeignKey('rooms.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    # 回滚顺序与升级相反
    op.drop_table('orders')
    op.drop_table('tenants')
    op.drop_table('room_transfers')
    op.drop_table('building_staff')

    # 恢复 rooms → properties
    op.rename_table('rooms', 'properties')
    op.rename_table('room_images', 'property_images')
    op.execute("ALTER TABLE property_images RENAME COLUMN room_id TO property_id")
    op.drop_constraint('fk_rooms_unit_type', 'properties', type_='foreignkey')
    op.drop_column('properties', 'unit_type_id')
    op.drop_column('properties', 'special_discount')
    # 恢复旧列 (简化回滚，仅允许结构回退)
    op.add_column('properties', sa.Column('title', sa.String(200), nullable=True))
    op.add_column('properties', sa.Column('address', sa.String(300), nullable=True))
    op.add_column('properties', sa.Column('district', sa.String(100), nullable=True))
    op.add_column('properties', sa.Column('price_monthly', sa.Numeric(12, 2), nullable=True))

    # 恢复 unit_types → room_types
    op.rename_table('unit_types', 'room_types')
    op.drop_constraint('fk_unit_types_institute', 'room_types', type_='foreignkey')
    op.drop_column('room_types', 'institute_id')
    op.drop_column('room_types', 'hall_count')
    op.drop_column('room_types', 'base_rent')
    op.drop_column('room_types', 'floor_pricing')
    op.add_column('room_types', sa.Column('property_id', sa.Integer(), nullable=True))
    op.add_column('room_types', sa.Column('price_monthly', sa.Numeric(12, 2), nullable=True))

    # institutes
    op.drop_index('ix_institutes_business_id', table_name='institutes')
    op.drop_column('institutes', 'business_id')

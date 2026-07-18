"""add_room_types_table

Revision ID: 8eac4d4ef2cd
Revises: 29216c392871
Create Date: 2026-07-16 12:52:17.989604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '8eac4d4ef2cd'
down_revision: Union[str, None] = '29216c392871'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 room_types 表 + 从现有 properties 迁移数据"""
    op.create_table('room_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('room_type', sa.Enum('studio', 'ensuite', '1bed', '2bed', '3bed+', 'shared', name='room_type_enum'), nullable=False),
        sa.Column('bedrooms', sa.Integer(), nullable=False),
        sa.Column('bathrooms', sa.Integer(), nullable=False),
        sa.Column('price_monthly', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('area_sqm', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('available_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('available_from', sa.Date(), nullable=True),
        sa.Column('min_stay_months', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('deposit_amount', sa.Integer(), nullable=True),
        sa.Column('deposit_type', sa.Enum('one_month', 'one_three', 'two_month', 'three_month', 'half_month', 'free', 'custom', name='room_type_deposit_type'), nullable=True),
        sa.Column('amenities', postgresql.ARRAY(sa.String(length=30)), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('available', 'rented', 'maintenance', name='room_type_status'), nullable=False, server_default='available'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_room_types_id'), 'room_types', ['id'], unique=False)
    op.create_index(op.f('ix_room_types_property_id'), 'room_types', ['property_id'], unique=False)

    # 数据迁移：每个现有 Property → 1 个 RoomType
    # deposit_type 用 ::text 中转避免 PostgreSQL 枚举直接转换报错
    op.execute("""
        INSERT INTO room_types (property_id, name, room_type, bedrooms, bathrooms,
            price_monthly, area_sqm, floor, amenities, available_from,
            min_stay_months, deposit_amount, deposit_type, status, available_count)
        SELECT
            p.id,
            CASE
                WHEN p.property_type = 'studio' THEN 'Studio'
                WHEN p.property_type = 'apartment' THEN 'Ensuite'
                WHEN p.property_type = 'house' THEN '1 Bed'
                WHEN p.property_type = 'shared' THEN 'Shared'
                ELSE 'Standard Room'
            END,
            CASE
                WHEN p.property_type = 'studio' THEN 'studio'::room_type_enum
                WHEN p.property_type = 'apartment' THEN 'ensuite'::room_type_enum
                WHEN p.property_type = 'house' THEN '1bed'::room_type_enum
                WHEN p.property_type = 'shared' THEN 'shared'::room_type_enum
                ELSE 'studio'::room_type_enum
            END,
            COALESCE(p.bedrooms, 0),
            COALESCE(p.bathrooms, 1),
            p.price_monthly,
            p.area_sqm,
            p.floor,
            p.amenities,
            p.available_from,
            COALESCE(p.min_stay_months, 3),
            p.deposit_amount,
            CASE
                WHEN p.deposit_type::text = 'one_month' THEN 'one_month'::room_type_deposit_type
                WHEN p.deposit_type::text = 'two_month' THEN 'two_month'::room_type_deposit_type
                WHEN p.deposit_type::text = 'three_month' THEN 'three_month'::room_type_deposit_type
                WHEN p.deposit_type::text = 'half_month' THEN 'half_month'::room_type_deposit_type
                WHEN p.deposit_type::text = 'free' THEN 'free'::room_type_deposit_type
                WHEN p.deposit_type::text = 'custom' THEN 'custom'::room_type_deposit_type
                ELSE NULL
            END,
            CASE
                WHEN p.status::text = 'available' THEN 'available'::room_type_status
                WHEN p.status::text = 'rented' THEN 'rented'::room_type_status
                WHEN p.status::text = 'maintenance' THEN 'maintenance'::room_type_status
                ELSE 'available'::room_type_status
            END,
            1
        FROM properties p
        WHERE p.deleted_at IS NULL
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_room_types_property_id'), table_name='room_types')
    op.drop_index(op.f('ix_room_types_id'), table_name='room_types')
    op.drop_table('room_types')
    # 枚举类型由 SQLAlchemy 自动清理

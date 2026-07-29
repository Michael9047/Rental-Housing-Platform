"""cleanup_room_model_add_unit_type_images

Revision ID: 07de8c996fa3
Revises: 46533e6f90f2
Create Date: 2026-07-28 17:59:02.692992

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '07de8c996fa3'
down_revision: Union[str, None] = '46533e6f90f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 创建 unit_type_images 表 ──
    op.create_table('unit_type_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unit_type_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['unit_type_id'], ['unit_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filename'),
    )
    op.create_index(op.f('ix_unit_type_images_id'), 'unit_type_images', ['id'], unique=False)
    op.create_index(op.f('ix_unit_type_images_unit_type_id'), 'unit_type_images', ['unit_type_id'], unique=False)

    # ── 2. 删除 rooms 表废弃列 ──
    deprecated_cols = [
        'title', 'address', 'district', 'price_monthly', 'area_sqm',
        'bedrooms', 'bathrooms', 'property_type', 'deposit_amount',
        'deposit_type', 'service_fee_rate', 'description', 'country',
        'latitude', 'longitude', 'rent_type', 'rental_rules', 'embedding', 'city',
    ]
    for col in deprecated_cols:
        op.drop_column('rooms', col)

    # rooms.status: VARCHAR → Enum（先创建枚举类型，再变更列）
    room_status_enum = sa.Enum('available', 'pending_review', 'rented', 'maintenance', 'offline', name='room_status')
    room_status_enum.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE rooms ALTER COLUMN status TYPE room_status USING status::room_status")

    # ── 3. unit_types 改造 ──
    # 新增日期列
    op.add_column('unit_types', sa.Column('lease_start_date', sa.Date(), nullable=True))
    op.add_column('unit_types', sa.Column('lease_end_date', sa.Date(), nullable=True))

    # 删除旧 image_urls ARRAY
    op.drop_column('unit_types', 'image_urls')

    # 枚举重命名：旧的 room_type_status → unit_type_status
    op.execute("ALTER TYPE room_type_status RENAME TO unit_type_status")
    # 旧的 room_type_deposit_type → unit_type_deposit_type
    op.execute("ALTER TYPE room_type_deposit_type RENAME TO unit_type_deposit_type")

    # 类型变更：Numeric → Float
    op.execute("ALTER TABLE unit_types ALTER COLUMN base_rent TYPE DOUBLE PRECISION USING base_rent::numeric::double precision")
    op.execute("ALTER TABLE unit_types ALTER COLUMN area_sqm TYPE DOUBLE PRECISION USING area_sqm::numeric::double precision")
    op.execute("ALTER TABLE unit_types ALTER COLUMN deposit_amount TYPE DOUBLE PRECISION USING deposit_amount::double precision")


def downgrade() -> None:
    op.drop_index(op.f('ix_unit_type_images_unit_type_id'), table_name='unit_type_images')
    op.drop_index(op.f('ix_unit_type_images_id'), table_name='unit_type_images')
    op.drop_table('unit_type_images')

    # 恢复 unit_types
    op.drop_column('unit_types', 'lease_end_date')
    op.drop_column('unit_types', 'lease_start_date')
    op.add_column('unit_types', sa.Column('image_urls', sa.ARRAY(sa.String(500)), nullable=True))

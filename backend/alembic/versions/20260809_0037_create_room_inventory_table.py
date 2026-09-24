"""create_room_inventory_table

Revision ID: 20260809_0037
Revises: 20260809_0036
Create Date: 2026-08-12

创建 room_inventory 和 booking_room_assignments 表（BM 合约管理-房号确认队列所需）
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260809_0037'
down_revision: Union[str, None] = '20260809_0036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'room_inventory',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('institute_id', sa.Integer(), sa.ForeignKey('institutes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('unit_type_id', sa.Integer(), sa.ForeignKey('unit_types.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('room_number', sa.String(50), nullable=False),
        sa.Column('floor', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='available'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('institute_id', 'room_number', name='uq_room_inventory_institute_number'),
    )
    op.create_table(
        'booking_room_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('booking_id', sa.Integer(), sa.ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('room_id', sa.String(36), sa.ForeignKey('room_inventory.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('confirmed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('booking_id', name='uq_booking_room_assignment_booking'),
    )


def downgrade() -> None:
    op.drop_table('booking_room_assignments')
    op.drop_table('room_inventory')

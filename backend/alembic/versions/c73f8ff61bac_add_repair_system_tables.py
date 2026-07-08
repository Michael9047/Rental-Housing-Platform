"""add repair system tables

Revision ID: c73f8ff61bac
Revises: b78e3052e498
Create Date: 2026-07-07 11:37:53.322604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c73f8ff61bac'
down_revision: Union[str, None] = 'b78e3052e498'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 通知类型扩展 ──
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'repair_created'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'repair_assigned'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'repair_completed'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'repair_status_change'")

    # ── repair_workers 表 ──
    op.create_table('repair_workers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('manager_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('available', 'working', 'on_leave', name='worker_status'), nullable=False, server_default='available'),
        sa.Column('skills', sa.JSON(), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('total_jobs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rating', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_repair_workers_id'), 'repair_workers', ['id'], unique=False)
    op.create_index(op.f('ix_repair_workers_manager_id'), 'repair_workers', ['manager_id'], unique=False)
    op.create_index(op.f('ix_repair_workers_user_id'), 'repair_workers', ['user_id'], unique=True)

    # ── repair_requests 表 ──
    op.create_table('repair_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('landlord_id', sa.Integer(), nullable=False),
        sa.Column('assigned_worker_id', sa.Integer(), nullable=True),
        sa.Column('issue_type', sa.Enum('plumbing', 'appliance', 'carpentry', 'wall_floor', 'plumbing_fixture', 'other', name='repair_issue_type'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('images', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'assigned', 'in_progress', 'completed', 'rejected', 'cancelled', name='repair_status'), nullable=False, server_default='pending'),
        sa.Column('scheduled_time', sa.String(length=32), nullable=True),
        sa.Column('completed_at', sa.String(length=32), nullable=True),
        sa.Column('work_record', sa.Text(), nullable=True),
        sa.Column('work_images', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assigned_worker_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['landlord_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_repair_requests_assigned_worker_id'), 'repair_requests', ['assigned_worker_id'], unique=False)
    op.create_index(op.f('ix_repair_requests_id'), 'repair_requests', ['id'], unique=False)
    op.create_index(op.f('ix_repair_requests_landlord_id'), 'repair_requests', ['landlord_id'], unique=False)
    op.create_index(op.f('ix_repair_requests_property_id'), 'repair_requests', ['property_id'], unique=False)
    op.create_index(op.f('ix_repair_requests_status'), 'repair_requests', ['status'], unique=False)
    op.create_index(op.f('ix_repair_requests_tenant_id'), 'repair_requests', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_repair_requests_tenant_id'), table_name='repair_requests')
    op.drop_index(op.f('ix_repair_requests_status'), table_name='repair_requests')
    op.drop_index(op.f('ix_repair_requests_property_id'), table_name='repair_requests')
    op.drop_index(op.f('ix_repair_requests_landlord_id'), table_name='repair_requests')
    op.drop_index(op.f('ix_repair_requests_id'), table_name='repair_requests')
    op.drop_index(op.f('ix_repair_requests_assigned_worker_id'), table_name='repair_requests')
    op.drop_table('repair_requests')
    op.drop_index(op.f('ix_repair_workers_user_id'), table_name='repair_workers')
    op.drop_index(op.f('ix_repair_workers_manager_id'), table_name='repair_workers')
    op.drop_index(op.f('ix_repair_workers_id'), table_name='repair_workers')
    op.drop_table('repair_workers')

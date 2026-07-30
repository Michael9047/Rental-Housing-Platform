"""add_notification_delivery_and_entity_refs

Revision ID: ntf_delivery_001
Revises: 1dae7a92bd3f
Create Date: 2026-07-23 10:00:00.000000

变更：
1. notifications 表新增 entity_type, entity_id, order_id, agreement_id, property_id
2. notification_deliveries 新表（投递记录 / Outbox）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ntf_delivery_001'
down_revision: Union[str, None] = '1dae7a92bd3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 站内通知表新增结构化关联字段 ────────────────────────
    op.add_column('notifications', sa.Column('entity_type', sa.String(30), nullable=True))
    op.add_column('notifications', sa.Column('entity_id', sa.String(36), nullable=True))
    op.add_column('notifications', sa.Column('order_id', sa.Integer(), nullable=True))
    op.add_column('notifications', sa.Column('agreement_id', sa.String(36), nullable=True))
    op.add_column('notifications', sa.Column('property_id', sa.Integer(), nullable=True))

    op.create_index(op.f('ix_notifications_order_id'), 'notifications', ['order_id'])
    op.create_index(op.f('ix_notifications_property_id'), 'notifications', ['property_id'])
    op.create_foreign_key(
        'fk_notifications_order_id', 'notifications', 'orders',
        ['order_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_notifications_property_id', 'notifications', 'rooms',
        ['property_id'], ['id'], ondelete='SET NULL',
    )

    # 将 type 列从枚举改为 varchar(50)，以支持新旧两种事件类型
    op.alter_column('notifications', 'type',
                    existing_type=sa.Enum('booking_created','booking_approved','booking_rejected',
                        'booking_cancelled','booking_completed','payment_received','payment_created',
                        'payment_failed','payment_expired','contract_generated','contract_signed',
                        'auth_registration','auth_password_reset','repair_created','repair_assigned',
                        'repair_completed','repair_status_change','system',
                        name='notification_type'),
                    type_=sa.String(50),
                    existing_nullable=False)
    op.create_index(op.f('ix_notifications_type'), 'notifications', ['type'])

    # ── 2. 通知投递记录表（Outbox / 可靠性追踪）────────────────
    op.create_table('notification_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notification_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('template_id', sa.String(100), nullable=True),
        sa.Column('template_version', sa.String(20), nullable=True),
        sa.Column('recipient_masked', sa.String(100), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error_code', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
    )
    op.create_index(op.f('ix_notification_deliveries_id'), 'notification_deliveries', ['id'])
    op.create_index(op.f('ix_notification_deliveries_user_id'), 'notification_deliveries', ['user_id'])
    op.create_index(op.f('ix_notification_deliveries_notification_id'), 'notification_deliveries', ['notification_id'])
    op.create_index(op.f('ix_notification_deliveries_order_id'), 'notification_deliveries', ['order_id'])
    op.create_index(op.f('ix_notification_deliveries_channel'), 'notification_deliveries', ['channel'])
    op.create_index(op.f('ix_notification_deliveries_event_type'), 'notification_deliveries', ['event_type'])
    op.create_index(op.f('ix_notification_deliveries_status'), 'notification_deliveries', ['status'])
    op.create_unique_constraint('uq_notification_deliveries_idempotency', 'notification_deliveries', ['idempotency_key'])


def downgrade() -> None:
    # ── 2. 删除投递记录表 ────────────────────────────────────
    op.drop_table('notification_deliveries')

    # ── 1. 回滚通知表变更 ────────────────────────────────────
    op.drop_constraint('fk_notifications_property_id', 'notifications', type_='foreignkey')
    op.drop_constraint('fk_notifications_order_id', 'notifications', type_='foreignkey')
    op.drop_index(op.f('ix_notifications_property_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_order_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_type'), table_name='notifications')

    op.alter_column('notifications', 'type',
                    existing_type=sa.String(50),
                    type_=sa.Enum('booking_created','booking_approved','booking_rejected',
                        'booking_cancelled','booking_completed','payment_received','payment_created',
                        'payment_failed','payment_expired','contract_generated','contract_signed',
                        'auth_registration','auth_password_reset','repair_created','repair_assigned',
                        'repair_completed','repair_status_change','system',
                        name='notification_type'),
                    existing_nullable=False,
                    postgresql_using='type::notification_type')

    op.drop_column('notifications', 'property_id')
    op.drop_column('notifications', 'agreement_id')
    op.drop_column('notifications', 'order_id')
    op.drop_column('notifications', 'entity_id')
    op.drop_column('notifications', 'entity_type')

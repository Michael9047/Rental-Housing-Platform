"""add_pms_connections

Revision ID: f7ca5aa62eee
Revises: 20260708_0012_add_rent_type_to_properties
Create Date: 2026-07-09 05:31:31.020874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f7ca5aa62eee'
down_revision: Union[str, None] = '20260708_0012_add_rent_type_to_properties'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('pms_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institute_id', sa.Integer(), nullable=False),
        sa.Column('pms_type', sa.Enum('starrez', 'mews', 'cloudbeds', 'ota_xml', 'custom', name='pms_type'), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('api_key', sa.String(length=500), nullable=True),
        sa.Column('webhook_secret', sa.String(length=200), nullable=True),
        sa.Column('field_map_overrides', sa.JSON(), nullable=True),
        sa.Column('room_type_mapping', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sync_status', sa.Enum('idle', 'syncing', 'success', 'failed', 'pending_review', name='pms_sync_status'), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('total_properties_synced', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['institute_id'], ['institutes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pms_connections_id'), 'pms_connections', ['id'], unique=False)
    op.create_index(op.f('ix_pms_connections_institute_id'), 'pms_connections', ['institute_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pms_connections_institute_id'), table_name='pms_connections')
    op.drop_index(op.f('ix_pms_connections_id'), table_name='pms_connections')
    op.drop_table('pms_connections')
    # 同时删除两个枚举类型
    op.execute("DROP TYPE IF EXISTS pms_type")
    op.execute("DROP TYPE IF EXISTS pms_sync_status")

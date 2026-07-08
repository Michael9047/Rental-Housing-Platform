"""add amenities, available_from, min_stay, deposit_type, version, deleted_at

Revision ID: 6df040ea2aeb
Revises: 349ef87cce3a
Create Date: 2026-07-07 16:53:06.996266
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '6df040ea2aeb'
down_revision: Union[str, None] = '349ef87cce3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 deposit_type 枚举类型
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deposit_type AS ENUM (
                'one_month', 'one_three', 'two_month', 'three_month',
                'half_month', 'free', 'custom'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.add_column('properties', sa.Column('amenities', postgresql.ARRAY(sa.String(length=30)), nullable=True))
    op.add_column('properties', sa.Column('available_from', sa.Date(), nullable=True))
    op.add_column('properties', sa.Column('min_stay_months', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('properties', sa.Column('deposit_type', postgresql.ENUM('one_month', 'one_three', 'two_month', 'three_month', 'half_month', 'free', 'custom', name='deposit_type', create_type=False), nullable=True))
    op.add_column('properties', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('properties', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_properties_deleted_at'), 'properties', ['deleted_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_properties_deleted_at'), table_name='properties')
    op.drop_column('properties', 'deleted_at')
    op.drop_column('properties', 'version')
    op.drop_column('properties', 'deposit_type')
    op.execute("DROP TYPE IF EXISTS deposit_type")
    op.drop_column('properties', 'min_stay_months')
    op.drop_column('properties', 'available_from')
    op.drop_column('properties', 'amenities')

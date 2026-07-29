"""add_business_id_and_remove_room_institute_id

Revision ID: 8e815cebb8be
Revises: 983b708fb08f
Create Date: 2026-07-28 17:30:54.721750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '8e815cebb8be'
down_revision: Union[str, None] = '983b708fb08f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 删除 rooms 上的冗余 institute_id 列和索引
    op.drop_index('ix_rooms_institute_id', table_name='rooms', if_exists=True)
    op.drop_column('rooms', 'institute_id')

    # 2. rooms 表新增 business_id
    op.add_column('rooms', sa.Column('business_id', sa.String(length=24), nullable=True))
    op.create_index(op.f('ix_rooms_business_id'), 'rooms', ['business_id'], unique=True)

    # 3. unit_types 表新增 business_id
    op.add_column('unit_types', sa.Column('business_id', sa.String(length=24), nullable=True))
    op.create_index(op.f('ix_unit_types_business_id'), 'unit_types', ['business_id'], unique=True)


def downgrade() -> None:
    # 回滚 unit_types
    op.drop_index(op.f('ix_unit_types_business_id'), table_name='unit_types')
    op.drop_column('unit_types', 'business_id')

    # 回滚 rooms
    op.drop_index(op.f('ix_rooms_business_id'), table_name='rooms')
    op.drop_column('rooms', 'business_id')

    # 回滚 institute_id
    op.add_column('rooms', sa.Column('institute_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_index('ix_rooms_institute_id', 'rooms', ['institute_id'], unique=False)

"""Room 添加 building_block 字段 — 多栋公寓区场景下的楼栋标识

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms',
        sa.Column('building_block', sa.String(20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('rooms', 'building_block')

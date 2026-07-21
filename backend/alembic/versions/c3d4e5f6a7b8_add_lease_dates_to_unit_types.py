"""UnitType 添加起租/止租时间字段

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('unit_types',
        sa.Column('lease_start', sa.String(50), nullable=True)
    )
    op.add_column('unit_types',
        sa.Column('lease_end', sa.String(50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('unit_types', 'lease_end')
    op.drop_column('unit_types', 'lease_start')

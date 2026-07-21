"""UnitType 添加货币 + 专属优惠字段

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('unit_types',
        sa.Column('currency', sa.String(10), nullable=True, server_default=sa.text("'CNY'"))
    )
    op.add_column('unit_types',
        sa.Column('special_offer', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('unit_types', 'special_offer')
    op.drop_column('unit_types', 'currency')

"""mvp_enhancements_image_urls_deposit_status

Revision ID: 3ef8cf1ad777
Revises: 20260719_0100
Create Date: 2026-07-20 17:17:01.623635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '3ef8cf1ad777'
down_revision: Union[str, None] = '20260719_0100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 户型图片URL数组
    op.add_column('unit_types', sa.Column('image_urls', postgresql.ARRAY(sa.String(length=500)), nullable=True))
    # 订单押金状态
    op.add_column('orders', sa.Column('deposit_status', sa.String(length=20), nullable=False, server_default='unpaid'))


def downgrade() -> None:
    op.drop_column('orders', 'deposit_status')
    op.drop_column('unit_types', 'image_urls')

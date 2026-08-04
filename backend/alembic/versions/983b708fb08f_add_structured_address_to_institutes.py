"""add_structured_address_to_institutes

Revision ID: 983b708fb08f
Revises: d625946f53a4
Create Date: 2026-07-27 15:19:54.554350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '983b708fb08f'
down_revision: Union[str, None] = 'd625946f53a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 institutes 表新增结构化地址字段（country/city/district 已存在，仅补 street + postal_code）"""
    op.add_column('institutes', sa.Column('street', sa.String(length=200), nullable=True))
    op.add_column('institutes', sa.Column('postal_code', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """回退 — 删除 street + postal_code"""
    op.drop_column('institutes', 'postal_code')
    op.drop_column('institutes', 'street')

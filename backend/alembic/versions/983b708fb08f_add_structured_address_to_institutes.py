"""add_structured_address_to_institutes

Revision ID: 983b708fb08f
Revises: f40a63c630f9
Create Date: 2026-07-27 15:19:54.554350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '983b708fb08f'
down_revision: Union[str, None] = 'f40a63c630f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 institutes 表新增结构化地址字段"""
    op.add_column('institutes', sa.Column('country', sa.String(length=100), nullable=True))
    op.add_column('institutes', sa.Column('city', sa.String(length=100), nullable=True))
    op.add_column('institutes', sa.Column('district', sa.String(length=100), nullable=True))
    op.add_column('institutes', sa.Column('street', sa.String(length=200), nullable=True))
    op.add_column('institutes', sa.Column('postal_code', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """回退 — 删除结构化地址字段"""
    op.drop_column('institutes', 'postal_code')
    op.drop_column('institutes', 'street')
    op.drop_column('institutes', 'district')
    op.drop_column('institutes', 'city')
    op.drop_column('institutes', 'country')

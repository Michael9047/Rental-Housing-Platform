"""add_name_cn_abbreviation_lat_lng_to_institutes

Revision ID: 29216c392871
Revises: bbc80e96579d
Create Date: 2026-07-15 20:54:02.107250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '29216c392871'
down_revision: Union[str, None] = 'bbc80e96579d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 institutes 表添加中文名、缩写和地理坐标字段"""
    op.add_column('institutes', sa.Column('name_cn', sa.String(length=200), nullable=True))
    op.add_column('institutes', sa.Column('abbreviation', sa.String(length=50), nullable=True))
    op.add_column('institutes', sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('institutes', sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True))


def downgrade() -> None:
    op.drop_column('institutes', 'longitude')
    op.drop_column('institutes', 'latitude')
    op.drop_column('institutes', 'abbreviation')
    op.drop_column('institutes', 'name_cn')

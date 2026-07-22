"""add_country_to_properties

Revision ID: ca93d74c7008
Revises: d8b5afa15531
Create Date: 2026-07-12 16:07:14.942789

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = 'ca93d74c7008'
down_revision: Union[str, None] = 'd8b5afa15531'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COUNTRY_ENUM = sa.Enum('CN', 'HK', 'MO', 'TW', 'SG', 'GB', 'US', 'AU', 'DE', 'FR', 'NL', 'CA', 'JP', 'KR', 'OTHER', name='country_code')


def upgrade() -> None:
    # 旧分支已经通过 20260706_0011 以 VARCHAR 形式添加过 country。
    # 合并迁移历史时保留现有列，避免重复添加导致升级中断。
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("properties")}
    if "country" in columns:
        return
    COUNTRY_ENUM.create(op.get_bind(), checkfirst=True)
    op.add_column('properties', sa.Column(
        'country', COUNTRY_ENUM,
        nullable=False,
        server_default='CN',
    ))


def downgrade() -> None:
    op.drop_column('properties', 'country')
    COUNTRY_ENUM.drop(op.get_bind(), checkfirst=True)

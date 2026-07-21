"""amenities 升级 — 公寓/户型配套扩充 + 公寓新增 female_only / couples_allowed

Revision ID: a1b2c3d4e5f6
Revises: fe7b76a287e9
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4dc4f5252028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Institute 表新增特殊标记字段
    op.add_column('institutes',
        sa.Column('female_only', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )
    op.add_column('institutes',
        sa.Column('couples_allowed', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )

    # 2. amenities 数组扩容: institutes 表 30→50
    op.alter_column('institutes', 'amenities',
        existing_type=postgresql.ARRAY(sa.String(30)),
        type_=postgresql.ARRAY(sa.String(50)),
        existing_nullable=True,
        postgresql_using='amenities::varchar(50)[]'
    )

    # 3. amenities 数组扩容: unit_types 表 30→50
    op.alter_column('unit_types', 'amenities',
        existing_type=postgresql.ARRAY(sa.String(30)),
        type_=postgresql.ARRAY(sa.String(50)),
        existing_nullable=True,
        postgresql_using='amenities::varchar(50)[]'
    )


def downgrade() -> None:
    op.drop_column('institutes', 'couples_allowed')
    op.drop_column('institutes', 'female_only')

    op.alter_column('unit_types', 'amenities',
        existing_type=postgresql.ARRAY(sa.String(50)),
        type_=postgresql.ARRAY(sa.String(30)),
        existing_nullable=True,
        postgresql_using='amenities::varchar(30)[]'
    )

    op.alter_column('institutes', 'amenities',
        existing_type=postgresql.ARRAY(sa.String(50)),
        type_=postgresql.ARRAY(sa.String(30)),
        existing_nullable=True,
        postgresql_using='amenities::varchar(30)[]'
    )

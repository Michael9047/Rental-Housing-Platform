"""Room.special_discount numeric → text

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('rooms', 'special_discount',
        existing_type=sa.Numeric(12, 2),
        type_=sa.String(200),
        existing_nullable=True,
        postgresql_using='special_discount::varchar(200)'
    )


def downgrade() -> None:
    op.alter_column('rooms', 'special_discount',
        existing_type=sa.String(200),
        type_=sa.Numeric(12, 2),
        existing_nullable=True,
        postgresql_using='special_discount::numeric(12,2)'
    )

"""add_wechat_fields_to_users

Revision ID: a1b2c3d4e5f7
Revises: fe087f3eaffd
Create Date: 2026-08-04 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'fe087f3eaffd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('wechat', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('wechat_qr', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'wechat_qr')
    op.drop_column('users', 'wechat')

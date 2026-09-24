"""merge wechat_fields branch into main

Revision ID: 7ac813cadcec
Revises: 8fcc418f50f5, a1b2c3d4e5f7
Create Date: 2026-08-11 17:55:31.991708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7ac813cadcec'
down_revision: Union[str, None] = ('8fcc418f50f5', 'a1b2c3d4e5f7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

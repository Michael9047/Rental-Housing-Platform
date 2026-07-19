"""add accumulated_filters to chat_sessions

Revision ID: 20260719_0017
Revises: d8b5afa15531
Create Date: 2026-07-19
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers
revision: str = '20260719_0017'
down_revision: Union[str, None] = 'd8b5afa15531'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'chat_sessions',
        sa.Column('accumulated_filters', JSON, nullable=True)
    )


def downgrade() -> None:
    op.drop_column('chat_sessions', 'accumulated_filters')

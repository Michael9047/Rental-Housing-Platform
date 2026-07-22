"""chat_session user_id → nullable (支持游客会话)

Revision ID: 20260716_0015
Revises: 29216c392871
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260716_0015'
down_revision: Union[str, None] = '29216c392871'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('chat_sessions', 'user_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('chat_sessions', 'user_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)

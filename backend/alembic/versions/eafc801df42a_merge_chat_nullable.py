"""merge_chat_nullable

Revision ID: eafc801df42a
Revises: 20260716_0015, 8eac4d4ef2cd
Create Date: 2026-07-16 15:59:32.215551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'eafc801df42a'
down_revision: Union[str, None] = ('20260716_0015', '8eac4d4ef2cd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

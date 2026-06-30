"""merge migration heads after UI branch merge

Revision ID: 5ac4aa5f38f4
Revises: 20260620_0002, 20260626_0010
Create Date: 2026-06-26 16:45:10.353679

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5ac4aa5f38f4'
down_revision: Union[str, None] = ('20260620_0002', '20260626_0010')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

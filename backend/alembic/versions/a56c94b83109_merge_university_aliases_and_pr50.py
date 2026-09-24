"""merge_university_aliases_and_pr50

Revision ID: a56c94b83109
Revises: 20260809_0037, 403613adfb5a
Create Date: 2026-08-12 14:43:08.822128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a56c94b83109'
down_revision: Union[str, None] = ('20260809_0037', '403613adfb5a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

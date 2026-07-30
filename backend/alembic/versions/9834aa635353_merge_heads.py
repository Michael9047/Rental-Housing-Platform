"""merge_heads

Revision ID: 9834aa635353
Revises: 20260726_0034, 5c56852684be
Create Date: 2026-07-27 12:51:36.021931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9834aa635353'
down_revision: Union[str, None] = ('20260726_0034', '5c56852684be')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

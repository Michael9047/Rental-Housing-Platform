"""merge_branch_heads

Revision ID: fe087f3eaffd
Revises: 20260731_0039, 8c314438f8b1
Create Date: 2026-08-04 17:15:03.658078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fe087f3eaffd'
down_revision: Union[str, None] = ('20260731_0039', '8c314438f8b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

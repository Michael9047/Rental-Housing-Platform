"""merge_all_heads

Revision ID: d52d47faa4b4
Revises: ca93d74c7008, 20260717_0016, 20260719_0017
Create Date: 2026-07-19 14:58:18.381870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd52d47faa4b4'
down_revision: Union[str, None] = ('ca93d74c7008', '20260717_0016', '20260719_0017')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

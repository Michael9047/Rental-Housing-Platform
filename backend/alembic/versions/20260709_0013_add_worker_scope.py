"""add worker_scope to repair_workers

Revision ID: 20260709_0013
Revises: e5f6a7b8c9d0
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260709_0013'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE worker_scope AS ENUM ('platform', 'apartment')")
    op.add_column('repair_workers', sa.Column('scope', sa.Enum('platform', 'apartment', name='worker_scope'), nullable=False, server_default='apartment'))


def downgrade() -> None:
    op.drop_column('repair_workers', 'scope')
    op.execute("DROP TYPE worker_scope")

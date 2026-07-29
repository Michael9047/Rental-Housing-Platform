"""add_uuid_to_all_three_layers

Revision ID: 46533e6f90f2
Revises: 8e815cebb8be
Create Date: 2026-07-28 17:45:54.884702

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '46533e6f90f2'
down_revision: Union[str, None] = '8e815cebb8be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ['institutes', 'unit_types', 'rooms']:
        op.add_column(table, sa.Column('uuid', sa.String(length=36), nullable=True))
        op.create_unique_constraint(f'uq_{table}_uuid', table, ['uuid'])


def downgrade() -> None:
    for table in ['institutes', 'unit_types', 'rooms']:
        op.drop_constraint(f'uq_{table}_uuid', table, type_='unique')
        op.drop_column(table, 'uuid')

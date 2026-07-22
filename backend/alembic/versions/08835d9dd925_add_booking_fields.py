"""add booking fields

Revision ID: 08835d9dd925
Revises: 58b8a1a10a15
Create Date: 2026-07-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '08835d9dd925'
down_revision: Union[str, None] = '58b8a1a10a15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('lease_months', sa.Integer(), nullable=True))
    op.add_column('bookings', sa.Column('total_rent', sa.Integer(), nullable=True))
    op.add_column('bookings', sa.Column('application_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'application_data')
    op.drop_column('bookings', 'total_rent')
    op.drop_column('bookings', 'lease_months')

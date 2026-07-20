"""add compat fields to rooms

Revision ID: cc65d383b732
Revises: fe7b76a287e9
Create Date: 2026-07-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'cc65d383b732'
down_revision: Union[str, None] = 'fe7b76a287e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('title', sa.String(length=200), nullable=True))
    op.add_column('rooms', sa.Column('address', sa.String(length=500), nullable=True))
    op.add_column('rooms', sa.Column('district', sa.String(length=100), nullable=True))
    op.add_column('rooms', sa.Column('price_monthly', sa.Numeric(12, 2), nullable=True))
    op.add_column('rooms', sa.Column('area_sqm', sa.Numeric(8, 2), nullable=True))
    op.add_column('rooms', sa.Column('bedrooms', sa.Integer(), nullable=True))
    op.add_column('rooms', sa.Column('bathrooms', sa.Integer(), nullable=True))
    op.add_column('rooms', sa.Column('property_type', sa.String(length=50), nullable=True))
    op.add_column('rooms', sa.Column('deposit_amount', sa.Integer(), nullable=True))
    op.add_column('rooms', sa.Column('service_fee_rate', sa.Float(), nullable=True))
    op.add_column('rooms', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('rooms', 'description')
    op.drop_column('rooms', 'service_fee_rate')
    op.drop_column('rooms', 'deposit_amount')
    op.drop_column('rooms', 'property_type')
    op.drop_column('rooms', 'bathrooms')
    op.drop_column('rooms', 'bedrooms')
    op.drop_column('rooms', 'area_sqm')
    op.drop_column('rooms', 'price_monthly')
    op.drop_column('rooms', 'district')
    op.drop_column('rooms', 'address')
    op.drop_column('rooms', 'title')

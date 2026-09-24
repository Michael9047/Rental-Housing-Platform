"""add tenant profile fields and is_default

Revision ID: 20260804_tenant_fields
Revises: 20260804_rename_bm
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260804_tenant_fields'
down_revision: Union[str, None] = '20260804_rename_bm'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false', comment='是否默认租客'))
    op.add_column('tenants', sa.Column('enrollment_level', sa.String(50), nullable=True))
    op.add_column('tenants', sa.Column('enrollment_term', sa.String(20), nullable=True))
    op.add_column('tenants', sa.Column('student_classification', sa.String(50), nullable=True))
    op.add_column('tenants', sa.Column('preferred_name', sa.String(100), nullable=True))
    op.add_column('tenants', sa.Column('is_international', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('tenants', sa.Column('visa_type', sa.String(50), nullable=True))
    op.add_column('tenants', sa.Column('visa_expiry', sa.Date(), nullable=True))
    op.add_column('tenants', sa.Column('citizenship_country', sa.String(100), nullable=True))
    op.add_column('tenants', sa.Column('disability_needs', sa.String(500), nullable=True))
    op.add_column('tenants', sa.Column('dietary_needs', sa.String(500), nullable=True))
    op.add_column('tenants', sa.Column('gender_identity', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'gender_identity')
    op.drop_column('tenants', 'dietary_needs')
    op.drop_column('tenants', 'disability_needs')
    op.drop_column('tenants', 'citizenship_country')
    op.drop_column('tenants', 'visa_expiry')
    op.drop_column('tenants', 'visa_type')
    op.drop_column('tenants', 'is_international')
    op.drop_column('tenants', 'preferred_name')
    op.drop_column('tenants', 'student_classification')
    op.drop_column('tenants', 'enrollment_term')
    op.drop_column('tenants', 'enrollment_level')
    op.drop_column('tenants', 'is_default')

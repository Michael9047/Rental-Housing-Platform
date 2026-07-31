"""add_missing_unit_type_columns_business_id_uuid_dates

Revision ID: 8c314438f8b1
Revises: 4c660ac0e3e3
Create Date: 2026-07-31 13:02:32.072440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8c314438f8b1'
down_revision: Union[str, None] = '4c660ac0e3e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # unit_types: 补 business_id / uuid / 日期列
    op.add_column("unit_types", sa.Column("business_id", sa.String(24), nullable=True))
    op.create_index("ix_unit_types_business_id", "unit_types", ["business_id"], unique=True)
    op.add_column("unit_types", sa.Column("uuid", sa.String(36), nullable=True))
    op.create_index("ix_unit_types_uuid", "unit_types", ["uuid"], unique=True)
    op.add_column("unit_types", sa.Column("lease_start_date", sa.Date(), nullable=True))
    op.add_column("unit_types", sa.Column("lease_end_date", sa.Date(), nullable=True))

    # institutes: 补 uuid
    op.add_column("institutes", sa.Column("uuid", sa.String(36), nullable=True))
    op.create_index("ix_institutes_uuid", "institutes", ["uuid"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_institutes_uuid", table_name="institutes")
    op.drop_column("institutes", "uuid")

    op.drop_index("ix_unit_types_uuid", table_name="unit_types")
    op.drop_column("unit_types", "uuid")
    op.drop_index("ix_unit_types_business_id", table_name="unit_types")
    op.drop_column("unit_types", "business_id")
    op.drop_column("unit_types", "lease_end_date")
    op.drop_column("unit_types", "lease_start_date")

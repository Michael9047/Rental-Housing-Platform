"""合并当前迁移分支并补齐 Agent 房源检索所需字段。

Revision ID: 20260722_0018
Revises: 20260714_0013, 20260717_0016, 20260719_0017, ca93d74c7008
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260722_0018"
down_revision: Union[str, Sequence[str], None] = (
    "20260714_0013",
    "20260717_0016",
    "20260719_0017",
    "ca93d74c7008",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("properties")
    }

    if "min_lease_months" not in columns:
        op.add_column(
            "properties",
            sa.Column(
                "min_lease_months",
                sa.Integer(),
                nullable=False,
                server_default="12",
            ),
        )

    if "max_lease_months" not in columns:
        op.add_column(
            "properties",
            sa.Column(
                "max_lease_months",
                sa.Integer(),
                nullable=True,
                server_default="60",
            ),
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in inspect(op.get_bind()).get_columns("properties")
    }
    if "max_lease_months" in columns:
        op.drop_column("properties", "max_lease_months")
    if "min_lease_months" in columns:
        op.drop_column("properties", "min_lease_months")

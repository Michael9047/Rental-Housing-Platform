"""align_booking_flow_contract_storage

Revision ID: 20260813_0036
Revises: 20260804_0035, 8c314438f8b1
Create Date: 2026-08-13 00:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "20260813_0036"
down_revision: Union[str, tuple[str, str], None] = ("20260804_0035", "8c314438f8b1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _json_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    draft_columns = _columns("booking_flow_drafts")
    if "personal_info" not in draft_columns:
        op.add_column("booking_flow_drafts", sa.Column("personal_info", _json_type(), nullable=True))
    if "emergency_contact" not in draft_columns:
        op.add_column("booking_flow_drafts", sa.Column("emergency_contact", _json_type(), nullable=True))

    contract_columns = _columns("contracts")
    if "property_id" in contract_columns and op.get_bind().dialect.name != "sqlite":
        op.alter_column("contracts", "property_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    draft_columns = _columns("booking_flow_drafts")
    if "emergency_contact" in draft_columns:
        op.drop_column("booking_flow_drafts", "emergency_contact")
    if "personal_info" in draft_columns:
        op.drop_column("booking_flow_drafts", "personal_info")

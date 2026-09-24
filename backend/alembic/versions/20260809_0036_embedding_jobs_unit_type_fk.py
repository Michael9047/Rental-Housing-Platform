"""Point embedding job compatibility IDs at UnitType.

Revision ID: 20260809_0036
Revises: 20260804_0035, 8c314438f8b1
Create Date: 2026-08-09

``embedding_jobs.property_id`` remains named for API/task compatibility, but
new values reference ``unit_types.id`` after the Institute -> UnitType change.
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260809_0036"
down_revision: tuple[str, str] = ("20260804_0035", "8c314438f8b1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "embedding_jobs"
_COLUMN = "property_id"
_CONSTRAINT = "fk_embedding_jobs_property_id_unit_types"


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _foreign_keys() -> list[dict]:
    if not _has_table(_TABLE):
        return []
    return list(sa.inspect(op.get_bind()).get_foreign_keys(_TABLE))


def upgrade() -> None:
    if not _has_table(_TABLE) or not _has_table("unit_types"):
        return

    # PR2 removed the old properties table and its incoming constraints. Be
    # defensive for databases that reached this revision through another path.
    for foreign_key in _foreign_keys():
        if _COLUMN not in (foreign_key.get("constrained_columns") or []):
            continue
        name = foreign_key.get("name")
        referred_table = foreign_key.get("referred_table")
        if referred_table == "unit_types":
            return
        if name:
            op.drop_constraint(name, _TABLE, type_="foreignkey")

    # Keep legacy audit rows intact. PostgreSQL NOT VALID enforces the new
    # relationship for future writes without rejecting a deployment because an
    # old job points at a removed Property/Room ID. A later maintenance task can
    # re-index/clean those rows and validate the constraint separately.
    options = {"postgresql_not_valid": True} if op.get_bind().dialect.name == "postgresql" else {}
    op.create_foreign_key(
        _CONSTRAINT,
        _TABLE,
        "unit_types",
        [_COLUMN],
        ["id"],
        ondelete="CASCADE",
        **options,
    )


def downgrade() -> None:
    if not _has_table(_TABLE):
        return
    for foreign_key in _foreign_keys():
        if foreign_key.get("name") == _CONSTRAINT:
            op.drop_constraint(_CONSTRAINT, _TABLE, type_="foreignkey")
            break

    # The old properties table is intentionally not recreated here. Its
    # removal belongs to the earlier Institute/UnitType migration.

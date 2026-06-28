"""add pgvector extension and property embedding

Revision ID: 20260620_0002
Revises: 20260617_0001
Create Date: 2026-06-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "20260620_0002"
down_revision: Union[str, None] = "20260617_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "properties",
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index(
        "ix_properties_embedding_ivfflat",
        "properties",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_l2_ops"},
        postgresql_with={"lists": 100},
    )


def downgrade() -> None:
    op.drop_index("ix_properties_embedding_ivfflat", table_name="properties")
    op.drop_column("properties", "embedding")
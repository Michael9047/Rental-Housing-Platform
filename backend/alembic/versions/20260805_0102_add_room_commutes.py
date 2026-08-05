"""新增逐房源通勤预计算表。

Revision ID: 20260805_0102
Revises: 20260802_0101
Create Date: 2026-08-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_0102"
down_revision: Union[str, Sequence[str], None] = "20260802_0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 旧环境可能已是 vector 列但漏建索引；幂等补齐，避免语义检索全表扫描。
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_properties_embedding_hnsw "
        "ON properties USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unit_types_embedding_hnsw "
        "ON unit_types USING hnsw (embedding vector_cosine_ops)"
    )
    # 部分开发库可能已用最小 DDL 预建此表；正式迁移仍应可继续收口版本状态。
    if not sa.inspect(op.get_bind()).has_table("room_commutes"):
        op.create_table(
            "room_commutes",
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("university_id", sa.Integer(), nullable=False),
            sa.Column("transit_min", sa.Integer(), nullable=True),
            sa.Column("walk_min", sa.Integer(), nullable=True),
            sa.Column("drive_min", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(length=20), nullable=True),
            sa.Column(
                "computed_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["room_id"], ["properties.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["university_id"], ["universities.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("room_id", "university_id"),
        )
    op.create_index(
        "ix_room_commutes_university_id",
        "room_commutes",
        ["university_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_room_commutes_university_id",
        table_name="room_commutes",
    )
    op.drop_table("room_commutes")

"""unit_types.embedding Text→Vector(1536) + HNSW cosine 索引

Revision ID: 20260805_0100
Revises: 20260804_tenant_fields
Create Date: 2026-08-05

背景
────
- unit_types.embedding 目前是 Text 列（存 JSON 数组字符串如 "[0.1, 0.2, ...]"）。
- 搜索时需要拉取全部向量到应用层 NumPy 逐条算余弦，无法利用 ANN 索引。
- 本迁移将 embedding 改为 pgvector Vector(1536)，并建 HNSW cosine 索引，
  让向量排序下推到数据库（与 PR #43 的 Unit 12 PropertyService 配合）。

回填策略
────
历史 Text 值为 JSON 数组字符串，pgvector 可直接 ::vector 解析。
若存在维度不符/空串/损坏值 → 该行 embedding 留 NULL，由后续 re-embed 脚本重新生成。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260805_0100"
down_revision: Union[str, Sequence[str], None] = "20260804_tenant_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIM = 1536
EXPECTED_COMMAS = DIM - 1  # 1536 维向量的 JSON 字符串恰好有 1535 个逗号


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. 新增 Vector 列
    op.execute(f"ALTER TABLE unit_types ADD COLUMN embedding_vec vector({DIM})")

    # 2. 回填合法行（维度正确 + 非空 + 非损坏）
    op.execute(
        f"""
        UPDATE unit_types
        SET embedding_vec = embedding::vector({DIM})
        WHERE embedding IS NOT NULL
          AND btrim(embedding) <> ''
          AND (length(embedding) - length(replace(embedding, ',', ''))) = {EXPECTED_COMMAS}
        """
    )

    # 3. 丢弃旧 Text 列，新列改名为 embedding
    op.execute("ALTER TABLE unit_types DROP COLUMN embedding")
    op.execute("ALTER TABLE unit_types RENAME COLUMN embedding_vec TO embedding")

    # 4. HNSW cosine 索引（相比 ivfflat：无需预训练、召回更高、适合持续增长数据集）
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unit_types_embedding_hnsw "
        "ON unit_types USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_unit_types_embedding_hnsw")

    # vector → Text（存回 JSON 数组字符串形式）
    op.execute("ALTER TABLE unit_types ADD COLUMN embedding_txt text")
    op.execute(
        "UPDATE unit_types SET embedding_txt = embedding::text WHERE embedding IS NOT NULL"
    )
    op.execute("ALTER TABLE unit_types DROP COLUMN embedding")
    op.execute("ALTER TABLE unit_types RENAME COLUMN embedding_txt TO embedding")

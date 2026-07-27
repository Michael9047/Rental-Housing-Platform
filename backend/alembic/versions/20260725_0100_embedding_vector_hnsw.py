"""embedding Text→Vector(1536) + HNSW 索引，并合并三个 alembic head

Revision ID: 20260725_0100
Revises: 20260709_0014, 20260722_0033, 20260723_npc
Create Date: 2026-07-25

背景
────
- 迁移 20260620_0002 曾把 properties.embedding 建为 pgvector Vector(1536) 并建 ivfflat 索引；
- 迁移 1dae7a92bd3f 又把它 ALTER 回 Text 并删除了向量索引，导致向量检索退化为
  「SQL 捞 500 行 → 应用层 numpy 全量算余弦」，无法走 ANN 索引。
- 本迁移把 properties / unit_types 的 embedding 列改回 Vector(1536)，
  并建 HNSW（vector_cosine_ops）索引，让向量排序下推到数据库。

同时本仓库当前存在 3 个并行 alembic head（`alembic upgrade head` 会报多头错误），
本迁移一并合并它们。

回填策略（防止 prod 上 ALTER 因单行坏数据整体失败）
────
历史 Text 值为 JSON 数组字符串（如 "[0.1, 0.2, ...]"），pgvector 可直接 `::vector` 解析。
但若存在维度不符/空串/损坏值，直接 ALTER TYPE 会导致整表转换失败并回滚。
因此改为「新增向量列 → 仅回填逗号数=1535（即 1536 维）的合法行 → 丢弃旧列」。
无法安全回填的行留空（embedding IS NULL），由 reindex 任务/`--re-embed` 脚本重新生成。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260725_0100"
down_revision: Union[str, Sequence[str], None] = (
    "20260709_0014",
    "20260722_0033",
    "20260723_npc",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIM = 1536
# 1536 维向量的 JSON 字符串恰好有 1535 个逗号，用于过滤维度不符/损坏的历史值
EXPECTED_COMMAS = DIM - 1


def _text_to_vector(table: str) -> None:
    """将 {table}.embedding 从 Text 安全转换为 vector(1536)。"""
    op.execute(f"ALTER TABLE {table} ADD COLUMN embedding_vec vector({DIM})")
    op.execute(
        f"""
        UPDATE {table}
        SET embedding_vec = embedding::vector({DIM})
        WHERE embedding IS NOT NULL
          AND btrim(embedding) <> ''
          AND (length(embedding) - length(replace(embedding, ',', ''))) = {EXPECTED_COMMAS}
        """
    )
    op.execute(f"ALTER TABLE {table} DROP COLUMN embedding")
    op.execute(f"ALTER TABLE {table} RENAME COLUMN embedding_vec TO embedding")


def _vector_to_text(table: str) -> None:
    """降级：vector → Text（存回 JSON 数组字符串形式）。"""
    op.execute(f"ALTER TABLE {table} ADD COLUMN embedding_txt text")
    op.execute(
        f"UPDATE {table} SET embedding_txt = embedding::text WHERE embedding IS NOT NULL"
    )
    op.execute(f"ALTER TABLE {table} DROP COLUMN embedding")
    op.execute(f"ALTER TABLE {table} RENAME COLUMN embedding_txt TO embedding")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # properties（Room 表）与 unit_types 均携带 embedding 列
    for table in ("properties", "unit_types"):
        _text_to_vector(table)

    # HNSW 索引（cosine）——embedding 未归一化，用 cosine 与检索侧 <=> 保持一致。
    # HNSW 相比 ivfflat：无需预训练、数据增长无需重建、召回更高，适合持续增长的数据集。
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_properties_embedding_hnsw "
        "ON properties USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unit_types_embedding_hnsw "
        "ON unit_types USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_unit_types_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_properties_embedding_hnsw")
    for table in ("properties", "unit_types"):
        _vector_to_text(table)

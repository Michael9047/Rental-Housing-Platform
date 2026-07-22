"""修复房源国家字段枚举并合并迁移分支

Revision ID: 20260722_0018
Revises: 20260717_0016, 20260719_0017, ca93d74c7008
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260722_0018"
down_revision: Union[str, Sequence[str], None] = (
    "20260717_0016",
    "20260719_0017",
    "ca93d74c7008",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 历史分支曾把 country 留为 varchar，但 ORM 已使用 country_code 枚举。
    op.execute(
        "CREATE TYPE country_code AS ENUM "
        "('CN','HK','MO','TW','SG','GB','US','AU','DE','FR','NL','CA','JP','KR','OTHER')"
    )
    op.execute("ALTER TABLE properties ALTER COLUMN country DROP DEFAULT")
    op.execute(
        "ALTER TABLE properties ALTER COLUMN country TYPE country_code "
        "USING country::text::country_code"
    )
    op.execute("ALTER TABLE properties ALTER COLUMN country SET DEFAULT 'CN'::country_code")


def downgrade() -> None:
    op.execute("ALTER TABLE properties ALTER COLUMN country DROP DEFAULT")
    op.execute(
        "ALTER TABLE properties ALTER COLUMN country TYPE varchar(2) "
        "USING country::text"
    )
    op.execute("ALTER TABLE properties ALTER COLUMN country SET DEFAULT 'CN'")
    op.execute("DROP TYPE country_code")

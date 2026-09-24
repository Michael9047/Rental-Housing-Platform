"""unit_types 新增 rental_requirements 文本字段（选填，替代起止租期）"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260730_0037"
down_revision: Union[str, None] = "20260730_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("unit_types", sa.Column("rental_requirements", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("unit_types", "rental_requirements")

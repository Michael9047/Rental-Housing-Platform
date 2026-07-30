"""building_staff 新增 wechat（微信号）和 wechat_qr（微信二维码图片文件名）"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260730_0038"
down_revision: Union[str, None] = "20260730_0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("building_staff", sa.Column("wechat", sa.String(100), nullable=True))
    op.add_column("building_staff", sa.Column("wechat_qr", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("building_staff", "wechat_qr")
    op.drop_column("building_staff", "wechat")

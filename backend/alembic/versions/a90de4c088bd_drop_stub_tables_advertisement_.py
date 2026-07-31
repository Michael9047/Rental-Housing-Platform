"""drop_stub_tables_advertisement_marketplace_news

Revision ID: a90de4c088bd
Revises: 20260730_pr2
Create Date: 2026-07-31 12:17:22.302919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a90de4c088bd'
down_revision: Union[str, None] = '20260730_pr2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除广告系统空壳
    op.drop_table("ad_impressions", if_exists=True)
    op.drop_table("advertisements", if_exists=True)

    # 删除二手交易空壳
    op.drop_table("marketplace_item_images", if_exists=True)
    op.drop_table("marketplace_messages", if_exists=True)
    op.drop_table("marketplace_comments", if_exists=True)
    op.drop_table("marketplace_reports", if_exists=True)
    op.drop_table("marketplace_items", if_exists=True)

    # 删除资讯内容空壳
    op.drop_table("news_articles", if_exists=True)


def downgrade() -> None:
    # 不重建空壳表，此迁移不可逆
    pass

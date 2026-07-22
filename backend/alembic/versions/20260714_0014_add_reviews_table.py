"""Add reviews table with dual-scoring (property + landlord).

公寓机构房源：单维度评价（仅 property_rating 必填）
个人房东房源：双维度评价（property_rating + landlord_rating 都填）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260714_0014"
down_revision: Union[str, None] = "20260713_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 如果 reviews 表已存在（来自其他分支的迁移），跳过创建
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "reviews" in inspector.get_table_names():
        return
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("landlord_id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=True),
        sa.Column("property_rating", sa.Integer(), nullable=False),
        sa.Column("property_comment", sa.Text(), nullable=True),
        sa.Column("property_images", postgresql.JSON(), nullable=True),
        sa.Column("landlord_rating", sa.Integer(), nullable=True),
        sa.Column("landlord_comment", sa.Text(), nullable=True),
        sa.Column("landlord_images", postgresql.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="review_status"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["landlord_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("booking_id"),
    )
    op.create_index(op.f("ix_reviews_booking_id"), "reviews", ["booking_id"])
    op.create_index(op.f("ix_reviews_landlord_id"), "reviews", ["landlord_id"])
    op.create_index(op.f("ix_reviews_property_id"), "reviews", ["property_id"])
    op.create_index(op.f("ix_reviews_tenant_id"), "reviews", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("reviews")
    op.execute("DROP TYPE IF EXISTS review_status")

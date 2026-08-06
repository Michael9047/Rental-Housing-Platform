"""为户型增加租金计价周期枚举字段。"""
from alembic import op
import sqlalchemy as sa


revision = "20260807_0041"
down_revision = "20260806_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    rent_period = sa.Enum("weekly", "monthly", name="rent_period")
    rent_period.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "unit_types",
        sa.Column(
            "rent_period",
            rent_period,
            nullable=False,
            server_default=sa.text("'monthly'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("unit_types", "rent_period")
    sa.Enum("weekly", "monthly", name="rent_period").drop(op.get_bind(), checkfirst=True)

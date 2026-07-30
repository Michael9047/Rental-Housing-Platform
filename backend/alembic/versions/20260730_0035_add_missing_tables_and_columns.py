"""补全缺失的表和列：universities、institute_commutes、users 学生档案列"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0035"
down_revision: Union[str, None] = "9bc74a9fddef"  # merge pr39
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 创建 universities 表 ──
    op.create_table(
        "universities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_cn", sa.String(200), nullable=True),
        sa.Column("abbreviation", sa.String(50), nullable=True),
        sa.Column("aliases", sa.ARRAY(sa.String(50)), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_hot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_universities_id", "universities", ["id"])

    # ── 2. 创建 institute_commutes 表 ──
    op.create_table(
        "institute_commutes",
        sa.Column("institute_id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("transit_min", sa.Integer(), nullable=True),
        sa.Column("walk_min", sa.Integer(), nullable=True),
        sa.Column("drive_min", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["institute_id"], ["institutes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("institute_id", "university_id"),
    )

    # ── 3. users 新增学生档案列 ──
    op.add_column("users", sa.Column("enrollment_level", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("enrollment_class", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("enrollment_term", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("school_name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("major", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("student_classification", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("is_international", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("visa_type", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("visa_expiry", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("nationality", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("citizenship_country", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("disability_needs", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("dietary_needs", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("gender_identity", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("preferred_name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferred_name")
    op.drop_column("users", "gender_identity")
    op.drop_column("users", "dietary_needs")
    op.drop_column("users", "disability_needs")
    op.drop_column("users", "citizenship_country")
    op.drop_column("users", "nationality")
    op.drop_column("users", "visa_expiry")
    op.drop_column("users", "visa_type")
    op.drop_column("users", "is_international")
    op.drop_column("users", "student_classification")
    op.drop_column("users", "major")
    op.drop_column("users", "school_name")
    op.drop_column("users", "enrollment_term")
    op.drop_column("users", "enrollment_class")
    op.drop_column("users", "enrollment_level")
    op.drop_table("institute_commutes")
    op.drop_index("ix_universities_id", table_name="universities")
    op.drop_table("universities")

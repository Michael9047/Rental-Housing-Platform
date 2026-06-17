"""initial users and properties

Revision ID: 20260617_0001
Revises:
Create Date: 2026-06-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260617_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = sa.Enum("tenant", "landlord", "admin", name="user_role")
user_status = sa.Enum("active", "disabled", "deleted", name="user_status")
property_type = sa.Enum("apartment", "house", "studio", "shared", name="property_type")
property_status = sa.Enum("available", "rented", "maintenance", "offline", name="property_status")


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    user_status.create(op.get_bind(), checkfirst=True)
    property_type.create(op.get_bind(), checkfirst=True)
    property_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("wechat_openid", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_wechat_openid"), "users", ["wechat_openid"], unique=True)

    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("landlord_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("price_monthly", sa.Numeric(12, 2), nullable=False),
        sa.Column("area_sqm", sa.Numeric(8, 2), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=False),
        sa.Column("bathrooms", sa.Integer(), nullable=False),
        sa.Column("property_type", property_type, nullable=False),
        sa.Column("status", property_status, nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("area_sqm IS NULL OR area_sqm > 0", name="ck_properties_area_sqm_positive"),
        sa.CheckConstraint("bathrooms >= 0", name="ck_properties_bathrooms_non_negative"),
        sa.CheckConstraint("bedrooms >= 0", name="ck_properties_bedrooms_non_negative"),
        sa.CheckConstraint("price_monthly >= 0", name="ck_properties_price_monthly_non_negative"),
        sa.ForeignKeyConstraint(["landlord_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_properties_district"), "properties", ["district"], unique=False)
    op.create_index("ix_properties_district_status", "properties", ["district", "status"], unique=False)
    op.create_index(op.f("ix_properties_id"), "properties", ["id"], unique=False)
    op.create_index(op.f("ix_properties_landlord_id"), "properties", ["landlord_id"], unique=False)
    op.create_index(op.f("ix_properties_status"), "properties", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_properties_status"), table_name="properties")
    op.drop_index(op.f("ix_properties_landlord_id"), table_name="properties")
    op.drop_index(op.f("ix_properties_id"), table_name="properties")
    op.drop_index("ix_properties_district_status", table_name="properties")
    op.drop_index(op.f("ix_properties_district"), table_name="properties")
    op.drop_table("properties")

    op.drop_index(op.f("ix_users_wechat_openid"), table_name="users")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    property_status.drop(op.get_bind(), checkfirst=True)
    property_type.drop(op.get_bind(), checkfirst=True)
    user_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)

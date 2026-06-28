"""add institutes + v1.5 v2 tables

Revision ID: 20260626_0010_institutes_v15_v2
Revises: 20260624_0009_extend_notification_type_enum
Create Date: 2026-06-26

This migration adds:
  1. institutes table (v1 gap fix) + institute_status enum
  2. institute_id FK on properties
  3. bd_manager role in user_role enum
  4. saved_searches table (v1.5)
  5. reviews table + review_status enum (v1.5)
  6. marketplace_* tables (v2: items, images, messages, comments, reports)
  7. news_articles table (v2)
  8. advertisements + ad_impressions tables (v2)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "20260626_0010"
down_revision: Union[str, None] = "20260624_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enums to create / modify
# ---------------------------------------------------------------------------

NEW_ENUMS = [
    ("institute_status", ("pending", "active", "suspended")),
    ("review_status", ("pending", "approved", "rejected")),
    ("marketplace_item_condition", ("new", "like_new", "good", "fair")),
    ("marketplace_item_status", ("active", "sold", "removed")),
    ("marketplace_report_status", ("pending", "resolved", "dismissed")),
    ("news_article_status", ("draft", "published", "archived")),
    ("advertisement_status", ("draft", "active", "paused", "ended", "rejected")),
]


def upgrade() -> None:
    # --- 1. Create new enums ---
    for name, values in NEW_ENUMS:
        sa_enum = postgresql.ENUM(*values, name=name, create_type=True)
        sa_enum.create(op.get_bind(), checkfirst=True)  # type: ignore[no-untyped-call]

    # --- 2. Add bd_manager to user_role enum ---
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'bd_manager'")

    # --- 3. Create institutes table ---
    op.create_table(
        "institutes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("has_api", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("api_config", postgresql.JSON(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "active", "suspended", name="institute_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_institutes_id", "institutes", ["id"])
    op.create_index("ix_institutes_created_by", "institutes", ["created_by"])

    # --- 4. Add institute_id to properties ---
    op.add_column("properties", sa.Column("institute_id", sa.Integer(), nullable=True))
    op.create_index("ix_properties_institute_id", "properties", ["institute_id"])
    op.create_foreign_key(
        "fk_properties_institute_id_institutes",
        "properties", "institutes",
        ["institute_id"], ["id"],
        ondelete="SET NULL",
    )

    # --- 5. Create saved_searches table ---
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("query_params", postgresql.JSON(), nullable=False),
        sa.Column("notify_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_searches_id", "saved_searches", ["id"])
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])

    # --- 6. Create reviews table ---
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institute_id", sa.Integer(), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "approved", "rejected", name="review_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )
    op.create_index("ix_reviews_id", "reviews", ["id"])
    op.create_index("ix_reviews_tenant_id", "reviews", ["tenant_id"])
    op.create_index("ix_reviews_institute_id", "reviews", ["institute_id"])
    op.create_index("ix_reviews_booking_id", "reviews", ["booking_id"])

    # --- 7. Create marketplace_items table ---
    op.create_table(
        "marketplace_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column(
            "condition",
            postgresql.ENUM("new", "like_new", "good", "fair", name="marketplace_item_condition", create_type=False),
            nullable=False,
            server_default="good",
        ),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("active", "sold", "removed", name="marketplace_item_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("moderation_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_items_id", "marketplace_items", ["id"])
    op.create_index("ix_marketplace_items_seller_id", "marketplace_items", ["seller_id"])
    op.create_index("ix_marketplace_items_category", "marketplace_items", ["category"])
    op.create_index("ix_marketplace_items_district", "marketplace_items", ["district"])
    op.create_index("ix_marketplace_items_status", "marketplace_items", ["status"])

    # --- 8. Create marketplace_item_images table ---
    op.create_table(
        "marketplace_item_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("marketplace_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_item_images_id", "marketplace_item_images", ["id"])
    op.create_index("ix_marketplace_item_images_item_id", "marketplace_item_images", ["item_id"])

    # --- 9. Create marketplace_messages table ---
    op.create_table(
        "marketplace_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receiver_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("marketplace_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("moderation_status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_messages_id", "marketplace_messages", ["id"])
    op.create_index("ix_marketplace_messages_sender_id", "marketplace_messages", ["sender_id"])
    op.create_index("ix_marketplace_messages_receiver_id", "marketplace_messages", ["receiver_id"])
    op.create_index("ix_marketplace_messages_item_id", "marketplace_messages", ["item_id"])

    # --- 10. Create marketplace_comments table ---
    op.create_table(
        "marketplace_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("marketplace_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("moderation_status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_comments_id", "marketplace_comments", ["id"])
    op.create_index("ix_marketplace_comments_item_id", "marketplace_comments", ["item_id"])
    op.create_index("ix_marketplace_comments_user_id", "marketplace_comments", ["user_id"])

    # --- 11. Create marketplace_reports table ---
    op.create_table(
        "marketplace_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("marketplace_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "resolved", "dismissed", name="marketplace_report_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_reports_id", "marketplace_reports", ["id"])
    op.create_index("ix_marketplace_reports_reporter_id", "marketplace_reports", ["reporter_id"])
    op.create_index("ix_marketplace_reports_item_id", "marketplace_reports", ["item_id"])
    op.create_index("ix_marketplace_reports_status", "marketplace_reports", ["status"])

    # --- 12. Create news_articles table ---
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("cover_image_url", sa.String(500), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("draft", "published", "archived", name="news_article_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("published_at", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_articles_id", "news_articles", ["id"])
    op.create_index("ix_news_articles_district", "news_articles", ["district"])
    op.create_index("ix_news_articles_category", "news_articles", ["category"])

    # --- 13. Create advertisements table ---
    op.create_table(
        "advertisements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("target_url", sa.String(500), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("placement", sa.String(50), nullable=False),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("cost_per_click", sa.Float(), nullable=True),
        sa.Column("start_date", sa.String(32), nullable=False),
        sa.Column("end_date", sa.String(32), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("draft", "active", "paused", "ended", "rejected", name="advertisement_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_advertisements_id", "advertisements", ["id"])
    op.create_index("ix_advertisements_district", "advertisements", ["district"])
    op.create_index("ix_advertisements_placement", "advertisements", ["placement"])
    op.create_index("ix_advertisements_status", "advertisements", ["status"])
    op.create_index("ix_advertisements_created_by", "advertisements", ["created_by"])

    # --- 14. Create ad_impressions table ---
    op.create_table(
        "ad_impressions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ad_id", sa.Integer(), sa.ForeignKey("advertisements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_impressions_id", "ad_impressions", ["id"])
    op.create_index("ix_ad_impressions_ad_id", "ad_impressions", ["ad_id"])
    op.create_index("ix_ad_impressions_user_id", "ad_impressions", ["user_id"])
    op.create_index("ix_ad_impressions_action", "ad_impressions", ["action"])


def downgrade() -> None:
    # --- Drop tables in reverse dependency order ---
    op.drop_table("ad_impressions")
    op.drop_table("advertisements")
    op.drop_table("news_articles")
    op.drop_table("marketplace_reports")
    op.drop_table("marketplace_comments")
    op.drop_table("marketplace_messages")
    op.drop_table("marketplace_item_images")
    op.drop_table("marketplace_items")
    op.drop_table("reviews")
    op.drop_table("saved_searches")

    # Remove institute_id from properties
    op.drop_constraint("fk_properties_institute_id_institutes", "properties", type_="foreignkey")
    op.drop_index("ix_properties_institute_id", table_name="properties")
    op.drop_column("properties", "institute_id")

    op.drop_table("institutes")

    # Remove bd_manager from user_role (PostgreSQL doesn't support removing enum values,
    # so we leave the type as-is in downgrade to avoid data loss)
    # The enum values are left intact.

    # Drop enums
    for name, _ in reversed(NEW_ENUMS):
        op.execute(f"DROP TYPE IF EXISTS {name}")

"""新增第三方嵌入式签署模板、请求与事件审计表。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260806_0037"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_signature_template_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institute_id", sa.Integer(), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="dropbox_sign"),
        sa.Column("provider_template_id", sa.String(128), nullable=False),
        sa.Column("signer_role", sa.String(100), nullable=False),
        sa.Column("field_mapping", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider", "provider_template_id", name="uq_signature_template_provider_id"),
    )
    op.create_index("ix_external_signature_template_bindings_institute_id", "external_signature_template_bindings", ["institute_id"])
    op.create_table(
        "external_signature_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_binding_id", sa.String(36), sa.ForeignKey("external_signature_template_bindings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="dropbox_sign"),
        sa.Column("provider_request_id", sa.String(128), nullable=False),
        sa.Column("provider_signature_id", sa.String(128)),
        sa.Column("mode", sa.String(20), nullable=False, server_default="embedded"),
        sa.Column("status", sa.String(32), nullable=False, server_default="awaiting_signature"),
        sa.Column("signer_email", sa.String(255), nullable=False),
        sa.Column("signer_name", sa.String(200), nullable=False),
        sa.Column("request_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.UniqueConstraint("provider", "provider_request_id", name="uq_signature_request_provider_id"),
    )
    op.create_index("ix_external_signature_requests_contract_id", "external_signature_requests", ["contract_id"])
    op.create_index("ix_external_signature_requests_template_binding_id", "external_signature_requests", ["template_binding_id"])
    op.create_index("ix_external_signature_requests_provider_signature_id", "external_signature_requests", ["provider_signature_id"])
    op.create_table(
        "external_signature_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("signature_request_id", sa.String(36), sa.ForeignKey("external_signature_requests.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(32), nullable=False, server_default="dropbox_sign"),
        sa.Column("provider_event_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("processing_error", sa.Text()),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_signature_event_provider_id"),
    )
    op.create_index("ix_external_signature_events_signature_request_id", "external_signature_events", ["signature_request_id"])


def downgrade() -> None:
    op.drop_index("ix_external_signature_events_signature_request_id", table_name="external_signature_events")
    op.drop_table("external_signature_events")
    op.drop_index("ix_external_signature_requests_provider_signature_id", table_name="external_signature_requests")
    op.drop_index("ix_external_signature_requests_template_binding_id", table_name="external_signature_requests")
    op.drop_index("ix_external_signature_requests_contract_id", table_name="external_signature_requests")
    op.drop_table("external_signature_requests")
    op.drop_index("ix_external_signature_template_bindings_institute_id", table_name="external_signature_template_bindings")
    op.drop_table("external_signature_template_bindings")

"""为合同增加不可变版本、编号、哈希和数据快照。

Revision ID: 20260722_0025
Revises: 20260722_0024
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0025"
down_revision: Union[str, None] = "20260722_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'contract_ready'")
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'contract_signed'")
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'payment_pending'")
    op.drop_constraint("contracts_booking_id_key", "contracts", type_="unique")
    op.add_column("contracts", sa.Column("agreement_number", sa.String(64), nullable=True))
    op.add_column("contracts", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("contracts", sa.Column("template_version", sa.String(32), nullable=False, server_default="2026.1"))
    op.add_column("contracts", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("contracts", sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("contracts", sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE contracts SET agreement_number = 'LEGACY-' || id, generated_at = created_at WHERE agreement_number IS NULL")
    op.alter_column("contracts", "agreement_number", nullable=False)
    op.create_unique_constraint("uq_contracts_booking_version", "contracts", ["booking_id", "version"])
    op.create_index("ux_contracts_agreement_number", "contracts", ["agreement_number"], unique=True)
    op.create_index("ix_contracts_content_hash", "contracts", ["content_hash"])
    op.create_table(
        "contract_signatures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agreement_id", sa.String(36), nullable=False, unique=True),
        sa.Column("agreement_version", sa.Integer(), nullable=False),
        sa.Column("agreement_content_hash", sa.String(64), nullable=False),
        sa.Column("tenant_user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_name", sa.String(200), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("property_timezone", sa.String(64), nullable=False),
        sa.Column("consent_text_version", sa.String(32), nullable=False),
        sa.Column("signature_object_key", sa.String(500), nullable=False),
        sa.Column("signature_hash", sa.String(64), nullable=False),
        sa.Column("signed_pdf_object_key", sa.String(500), nullable=False),
        sa.Column("ip_address", sa.String(64)), sa.Column("user_agent", sa.String(500)),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_contract_signatures_agreement_id", "contract_signatures", ["agreement_id"])
    op.create_index("ix_contract_signatures_tenant_user_id", "contract_signatures", ["tenant_user_id"])
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_contract_snapshot_mutation() RETURNS trigger AS $$
        BEGIN
          IF NEW.booking_id IS DISTINCT FROM OLD.booking_id
             OR NEW.agreement_number IS DISTINCT FROM OLD.agreement_number
             OR NEW.version IS DISTINCT FROM OLD.version
             OR NEW.template_version IS DISTINCT FROM OLD.template_version
             OR NEW.content IS DISTINCT FROM OLD.content
             OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
             OR NEW.snapshot IS DISTINCT FROM OLD.snapshot
             OR NEW.generated_at IS DISTINCT FROM OLD.generated_at THEN
            RAISE EXCEPTION 'generated contract content and snapshot are immutable';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
    """)
    op.execute("CREATE TRIGGER trg_contract_snapshot_immutable BEFORE UPDATE ON contracts FOR EACH ROW EXECUTE FUNCTION prevent_contract_snapshot_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_contract_snapshot_immutable ON contracts")
    op.execute("DROP FUNCTION IF EXISTS prevent_contract_snapshot_mutation")
    op.drop_index("ix_contract_signatures_tenant_user_id", table_name="contract_signatures")
    op.drop_index("ix_contract_signatures_agreement_id", table_name="contract_signatures")
    op.drop_table("contract_signatures")
    op.drop_index("ix_contracts_content_hash", table_name="contracts")
    op.drop_index("ux_contracts_agreement_number", table_name="contracts")
    op.drop_constraint("uq_contracts_booking_version", "contracts", type_="unique")
    op.drop_column("contracts", "generated_at")
    op.drop_column("contracts", "snapshot")
    op.drop_column("contracts", "content_hash")
    op.drop_column("contracts", "template_version")
    op.drop_column("contracts", "version")
    op.drop_column("contracts", "agreement_number")
    op.create_unique_constraint("contracts_booking_id_key", "contracts", ["booking_id"])

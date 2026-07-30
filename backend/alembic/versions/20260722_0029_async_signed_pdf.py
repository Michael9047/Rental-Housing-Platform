"""签署事务与 PDF 异步生成解耦。

Revision ID: 20260722_0029
Revises: 20260722_0028
"""
from alembic import op
import sqlalchemy as sa
revision="20260722_0029"; down_revision="20260722_0028"; branch_labels=None; depends_on=None

def upgrade() -> None:
    op.add_column("contracts",sa.Column("pdf_status",sa.String(20),nullable=False,server_default="not_generated"))
    op.add_column("contracts",sa.Column("pdf_last_error",sa.String(500)))
    op.alter_column("contract_signatures","signed_pdf_object_key",existing_type=sa.String(500),nullable=True)
    op.execute("UPDATE contracts SET pdf_status='ready' WHERE status='signed' AND file_path IS NOT NULL")

def downgrade() -> None:
    op.execute("UPDATE contract_signatures SET signed_pdf_object_key=signature_object_key WHERE signed_pdf_object_key IS NULL")
    op.alter_column("contract_signatures","signed_pdf_object_key",existing_type=sa.String(500),nullable=False)
    op.drop_column("contracts","pdf_last_error"); op.drop_column("contracts","pdf_status")

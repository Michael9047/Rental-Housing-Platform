import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text as SAText, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.mixins import TimestampMixin
from app.db.session import Base


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("booking_id", "version", name="uq_contracts_booking_version"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    template_name: Mapped[str] = mapped_column(String(100), default="standard_lease")
    agreement_number: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), default="2026.1", nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="generated", nullable=False
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_status: Mapped[str] = mapped_column(String(20), default="not_generated", nullable=False)
    pdf_last_error: Mapped[str | None] = mapped_column(String(500))

    booking: Mapped["Booking"] = relationship()
    tenant: Mapped["User"] = relationship(foreign_keys=[tenant_id])
    property: Mapped["Property"] = relationship()


class ContractSignature(TimestampMixin, Base):
    """租客对特定不可变合同版本的电子签名证据。"""

    __tablename__ = "contract_signatures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agreement_id: Mapped[str] = mapped_column(ForeignKey("contracts.id", ondelete="RESTRICT"), unique=True, index=True)
    agreement_version: Mapped[int] = mapped_column(Integer, nullable=False)
    agreement_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    tenant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    property_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_text_version: Mapped[str] = mapped_column(String(32), nullable=False)
    signature_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_pdf_object_key: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    agreement: Mapped["Contract"] = relationship()

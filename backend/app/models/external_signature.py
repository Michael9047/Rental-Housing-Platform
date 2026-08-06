"""第三方电子签署模板、请求与回调审计模型。"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base


class ExternalSignatureTemplateBinding(Base):
    __tablename__ = "external_signature_template_bindings"
    __table_args__ = (UniqueConstraint("provider", "provider_template_id", name="uq_signature_template_provider_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 为空时表示平台默认模板；指定公寓时覆盖默认模板。
    institute_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="dropbox_sign")
    provider_template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    signer_role: Mapped[str] = mapped_column(String(100), nullable=False)
    field_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ExternalSignatureRequest(Base):
    __tablename__ = "external_signature_requests"
    __table_args__ = (UniqueConstraint("provider", "provider_request_id", name="uq_signature_request_provider_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    template_binding_id: Mapped[str] = mapped_column(ForeignKey("external_signature_template_bindings.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="dropbox_sign")
    provider_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_signature_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="embedded")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="awaiting_signature")
    signer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    signer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    request_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalSignatureEvent(Base):
    __tablename__ = "external_signature_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_signature_event_provider_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signature_request_id: Mapped[str | None] = mapped_column(ForeignKey("external_signature_requests.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="dropbox_sign")
    provider_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

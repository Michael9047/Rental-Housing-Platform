"""合同签署服务 — 记录租客电子签名证据并推进订单状态。"""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.booking import BookingStatus
from app.models.contract import Contract, ContractSignature
from app.schemas.contract import ContractSignCreate
from app.services.private_object_storage import PrivateObjectStorage


class ContractSignError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ContractSigningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sign(
        self,
        contract_id: str,
        tenant_user_id: int,
        payload: ContractSignCreate,
        ip_address: str | None,
        user_agent: str | None,
    ) -> ContractSignature:
        contract = await self.session.get(Contract, contract_id)
        if not contract:
            raise ContractSignError("CONTRACT_NOT_FOUND", "合同不存在", 404)
        if contract.tenant_id != tenant_user_id:
            raise ContractSignError("ACCESS_DENIED", "无权签署该合同", 403)
        if contract.version != payload.agreement_version or contract.content_hash != payload.agreement_content_hash:
            raise ContractSignError("AGREEMENT_VERSION_MISMATCH", "合同内容已更新，请重新阅读最新版本后签署", 409)

        existing = await self.session.scalar(
            select(ContractSignature).where(
                ContractSignature.agreement_id == contract.id,
                ContractSignature.tenant_user_id == tenant_user_id,
            )
        )
        if existing:
            return existing

        signed_at = datetime.now(timezone.utc)
        signature_payload = {
            "agreement_id": contract.id,
            "agreement_version": contract.version,
            "tenant_user_id": tenant_user_id,
            "tenant_name": payload.tenant_name,
            "signed_at": signed_at.isoformat(),
            "strokes": [[point.model_dump() for point in stroke] for stroke in payload.strokes],
        }
        raw = json.dumps(signature_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        signature_hash = hashlib.sha256(raw).hexdigest()
        object_key = f"signatures/{contract.id}.json"
        PrivateObjectStorage().put(object_key, raw)

        record = ContractSignature(
            agreement_id=contract.id,
            agreement_version=contract.version,
            agreement_content_hash=contract.content_hash or "",
            tenant_user_id=tenant_user_id,
            tenant_name=payload.tenant_name,
            signed_at=signed_at,
            property_timezone=str((contract.snapshot or {}).get("property_timezone") or "UTC"),
            consent_text_version=payload.consent_text_version,
            signature_object_key=object_key,
            signature_hash=signature_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            idempotency_key=payload.idempotency_key,
        )
        self.session.add(record)
        contract.status = "signed"
        contract.signed_at = signed_at
        contract.pdf_status = "pending"
        booking = await self.session.get(Booking, contract.booking_id)
        if booking:
            booking.status = BookingStatus.payment_pending
        await self.session.commit()
        await self.session.refresh(record)
        return record

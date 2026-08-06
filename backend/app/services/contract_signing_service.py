"""电子合同签署服务。"""
import hashlib
import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, ContractSignature
from app.models.user import User
from app.schemas.contract import ContractSignCreate, ContractSignatureResponse
from app.services.lease_pricing_service import LeasePricingService
from app.services.private_object_storage import PrivateObjectStorage


class ContractSignError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


class ContractSigningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._storage = PrivateObjectStorage()

    async def sign(
        self,
        contract_id: str,
        user_id: int,
        payload: ContractSignCreate,
        ip: str | None,
        user_agent: str | None,
    ) -> ContractSignatureResponse:
        if not payload.name_confirmed or not payload.electronic_signature_consent:
            raise ContractSignError(422, "CONSENT_REQUIRED", "请确认姓名并同意电子签名")
        if not payload.strokes:
            raise ContractSignError(422, "SIGNATURE_EMPTY", "请先完成手写签名")

        contract = await self.session.get(Contract, contract_id)
        if not contract:
            raise ContractSignError(404, "CONTRACT_NOT_FOUND", "合同不存在")
        if contract.tenant_id != user_id:
            raise ContractSignError(403, "NOT_TENANT", "只有租客可以签署合同")

        # 幂等检查
        existing = await self.session.scalar(
            select(ContractSignature).where(
                ContractSignature.agreement_id == contract_id,
                ContractSignature.tenant_user_id == user_id,
            )
        )
        if existing and existing.agreement_content_hash == contract.content_hash:
            return ContractSignatureResponse(
                agreement_id=existing.agreement_id,
                agreement_version=existing.agreement_version,
                agreement_content_hash=existing.agreement_content_hash,
                tenant_user_id=existing.tenant_user_id,
                tenant_name=existing.tenant_name,
                signed_at=existing.signed_at,
                property_timezone=existing.property_timezone,
                consent_text_version=existing.consent_text_version,
                signature_hash=existing.signature_hash,
                pdf_status="ready",
            )

        tenant = await self.session.get(User, user_id)
        tenant_name = payload.tenant_name or (tenant.username if tenant else str(user_id))

        # 存储手写签名 SVG
        signature_svg = _render_signature_svg(payload.strokes)
        signature_hash = hashlib.sha256(signature_svg.encode()).hexdigest()
        signature_key = f"signatures/{contract_id}/v{contract.version}/{signature_hash[:12]}.svg"
        self._storage.put(signature_key, signature_svg.encode("utf-8"))

        now = datetime.now(timezone.utc)
        signature = ContractSignature(
            id=str(uuid.uuid4()),
            agreement_id=contract_id,
            agreement_version=contract.version,
            agreement_content_hash=contract.content_hash or "",
            tenant_user_id=user_id,
            tenant_name=tenant_name,
            signed_at=now,
            property_timezone="Asia/Shanghai",
            consent_text_version="2026.1",
            signature_object_key=signature_key,
            signature_hash=signature_hash,
            ip_address=ip,
            user_agent=user_agent,
            idempotency_key=f"{contract_id}:{user_id}:{contract.version}",
        )
        self.session.add(signature)

        # 更新合同状态
        contract.status = "signed"
        contract.signed_at = now

        # 更新预订状态
        from app.models.booking import Booking, BookingStatus
        booking = await self.session.get(Booking, contract.booking_id)
        if booking and booking.status == BookingStatus.contract_ready:
            booking.status = BookingStatus.contract_signed
            # 复用预订阶段已建立的租客档案，不创建重复租客账号或档案。
            from app.models.tenant import Tenant
            tenant_profile = await self.session.get(Tenant, booking.tenant_id) if booking.tenant_id else None
            if tenant_profile:
                contract_start = booking.contract_start or (
                    date.fromisoformat(booking.scheduled_date) if booking.scheduled_date else None
                )
                contract_end = booking.contract_end or (
                    LeasePricingService.add_calendar_months(contract_start, booking.lease_months)
                    if contract_start and booking.lease_months else None
                )
                if contract_start and not booking.contract_start:
                    booking.contract_start = contract_start
                if contract_end and not booking.contract_end:
                    booking.contract_end = contract_end
                tenant_profile.current_unit_type_id = booking.unit_type_id
                tenant_profile.room_number = booking.room_number
                tenant_profile.move_in_date = contract_start
                tenant_profile.move_out_date = contract_end
                tenant_profile.housing_status = "active"

        await self.session.commit()
        await self.session.refresh(signature)

        return ContractSignatureResponse(
            agreement_id=signature.agreement_id,
            agreement_version=signature.agreement_version,
            agreement_content_hash=signature.agreement_content_hash,
            tenant_user_id=signature.tenant_user_id,
            tenant_name=signature.tenant_name,
            signed_at=signature.signed_at,
            property_timezone=signature.property_timezone,
            consent_text_version=signature.consent_text_version,
            signature_hash=signature.signature_hash,
            pdf_status="pending",
        )


def _render_signature_svg(strokes: list[list]) -> str:
    """将签名笔画列表渲染为 SVG。支持 dict 或 Pydantic model。"""
    if not strokes:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"></svg>'
    def _x(pt): return pt.x if hasattr(pt, 'x') else pt['x']
    def _y(pt): return pt.y if hasattr(pt, 'y') else pt['y']
    all_points = [pt for stroke in strokes for pt in stroke]
    xs = [_x(p) for p in all_points]
    ys = [_y(p) for p in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w = max(max_x - min_x + 40, 100)
    h = max(max_y - min_y + 40, 50)
    paths = []
    for stroke in strokes:
        if not stroke:
            continue
        d = f'M {_x(stroke[0]) - min_x + 20},{_y(stroke[0]) - min_y + 20}'
        for pt in stroke[1:]:
            d += f' L {_x(pt) - min_x + 20},{_y(pt) - min_y + 20}'
        paths.append(f'<path d="{d}" fill="none" stroke="#1a1a2e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{"".join(paths)}</svg>'

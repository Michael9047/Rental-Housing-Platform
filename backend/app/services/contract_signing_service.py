"""电子合同签署、证据保存和订单状态推进服务。"""

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, ContractSignature
from app.models.user import User
from app.schemas.contract import ContractSignCreate, ContractSignatureResponse
from app.services.private_object_storage import PrivateObjectStorage


class ContractSignError(Exception):
    """可安全返回给签署接口调用方的业务错误。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


class ContractSigningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._storage = PrivateObjectStorage()

    @staticmethod
    def validate_strokes(payload: ContractSignCreate) -> tuple[int, float]:
        """拒绝未同意、敷衍笔迹和可能造成资源消耗的超大签名。"""
        if not payload.name_confirmed or not payload.electronic_signature_consent:
            raise ContractSignError(422, "CONSENT_REQUIRED", "请确认姓名并同意电子签名")
        points = [point for stroke in payload.strokes for point in stroke]
        if len(points) > 5000:
            raise ContractSignError(422, "SIGNATURE_TOO_LARGE", "签名笔迹数据过大")
        length = sum(
            ((current.x - previous.x) ** 2 + (current.y - previous.y) ** 2) ** 0.5
            for stroke in payload.strokes
            for previous, current in zip(stroke, stroke[1:])
        )
        if len(points) < 8 or length < 0.2:
            raise ContractSignError(422, "SIGNATURE_EMPTY", "请完成有效的手写签名")
        return len(points), length

    @staticmethod
    def _response(signature: ContractSignature, pdf_status: str) -> ContractSignatureResponse:
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
            pdf_status=pdf_status,
        )

    async def sign(
        self,
        contract_id: str,
        user_id: int,
        payload: ContractSignCreate,
        ip: str | None,
        user_agent: str | None,
    ) -> ContractSignatureResponse:
        self.validate_strokes(payload)
        contract = await self.session.get(Contract, contract_id)
        if not contract:
            raise ContractSignError(404, "CONTRACT_NOT_FOUND", "合同不存在")
        if contract.tenant_id != user_id:
            raise ContractSignError(403, "FORBIDDEN", "只有合同租客本人可以签署")
        if (
            payload.agreement_version != contract.version
            or payload.agreement_content_hash != contract.content_hash
        ):
            raise ContractSignError(409, "AGREEMENT_VERSION_MISMATCH", "合同版本已更新，请刷新后重新确认")

        existing = await self.session.scalar(
            select(ContractSignature).where(
                ContractSignature.tenant_user_id == user_id,
                or_(
                    ContractSignature.idempotency_key == payload.idempotency_key,
                    ContractSignature.agreement_id == contract_id,
                ),
            )
        )
        if existing and existing.agreement_content_hash == contract.content_hash:
            return self._response(existing, contract.pdf_status)
        if existing:
            raise ContractSignError(409, "IDEMPOTENCY_CONFLICT", "签署请求与已有记录冲突")

        tenant = await self.session.get(User, user_id)
        tenant_name = payload.tenant_name or (tenant.username if tenant else str(user_id))
        signature_svg = _render_signature_svg(payload.strokes)
        signature_hash = hashlib.sha256(signature_svg.encode("utf-8")).hexdigest()
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
            consent_text_version=payload.consent_text_version,
            signature_object_key=signature_key,
            signature_hash=signature_hash,
            ip_address=ip,
            user_agent=user_agent,
            idempotency_key=payload.idempotency_key,
        )
        self.session.add(signature)
        contract.status = "signed"
        contract.signed_at = now

        from app.models.booking import Booking, BookingStatus

        booking = await self.session.get(Booking, contract.booking_id)
        if booking and booking.status == BookingStatus.contract_ready:
            # 进入 contract_ready 前已经完成付款和 BM 房号确认；签署即为预订完成。
            booking.status = BookingStatus.completed
            booking.payment_expires_at = None
            from app.services.inventory_service import sync_unit_type_inventory

            await sync_unit_type_inventory(self.session, booking.unit_type_id)

        await self.session.commit()
        await self.session.refresh(signature)
        return self._response(signature, contract.pdf_status)


def _render_signature_svg(strokes: list[list]) -> str:
    """将归一化签名笔迹渲染为仅含路径的 SVG。"""
    all_points = [point for stroke in strokes for point in stroke]
    paths: list[str] = []
    for stroke in strokes:
        if not stroke:
            continue
        commands = [f"M {stroke[0].x * 300:.2f},{stroke[0].y * 100:.2f}"]
        commands.extend(f"L {point.x * 300:.2f},{point.y * 100:.2f}" for point in stroke[1:])
        paths.append(
            f'<path d="{" ".join(commands)}" fill="none" stroke="#1a1a2e" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    if not all_points:
        paths = []
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100" '
        f'viewBox="0 0 300 100">{"".join(paths)}</svg>'
    )

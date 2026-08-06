"""合同电子签名服务 — 笔迹校验、幂等、越权、版本校验、异步PDF生成"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract, ContractSignature
from app.schemas.contract import ContractSignCreate

logger = logging.getLogger(__name__)


class ContractSignError(Exception):
    """合同签署业务错误，携带 HTTP 状态码与错误码"""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class _InMemoryStorage:
    """简易签名对象存储（生产可替换为 S3/OSS）"""

    def put_immutable(self, key: str, data: bytes) -> None:
        logger.info("signature object stored: %s (%d bytes)", key, len(data))


class ContractSigningService:
    """合同签署服务"""

    MIN_STROKES = 8
    MIN_STROKE_LENGTH = 0.2
    MAX_POINTS = 3000

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.storage = _InMemoryStorage()

    # ── 笔迹校验 ──────────────────────────────────────
    @staticmethod
    def validate_strokes(payload: ContractSignCreate) -> tuple[int, float]:
        """校验签名笔迹：笔划数量、总长度、点数上限、同意确认"""
        if not payload.name_confirmed or not payload.electronic_signature_consent:
            raise ContractSignError(
                "CONSENT_REQUIRED", "请确认姓名并同意电子签名", status_code=422
            )
        total_points = sum(len(stroke) for stroke in payload.strokes)
        if total_points > ContractSigningService.MAX_POINTS:
            raise ContractSignError(
                "SIGNATURE_TOO_LARGE", "签名过于复杂，请重新签名", status_code=422
            )
        total_length = 0.0
        total_points = 0
        for stroke in payload.strokes:
            if len(stroke) < 2:
                continue
            total_points += len(stroke)
            for prev, cur in zip(stroke, stroke[1:]):
                total_length += ((cur.x - prev.x) ** 2 + (cur.y - prev.y) ** 2) ** 0.5
        if total_points < ContractSigningService.MIN_STROKES:
            raise ContractSignError(
                "SIGNATURE_EMPTY", "请先完成手写签名", status_code=422
            )
        if total_length < ContractSigningService.MIN_STROKE_LENGTH:
            raise ContractSignError(
                "SIGNATURE_EMPTY", "签名笔迹太短，请重新签名", status_code=422
            )
        return total_points, total_length

    # ── 签名主流程 ────────────────────────────────────
    async def sign(
        self,
        contract_id: str,
        tenant_user_id: int,
        payload: ContractSignCreate,
        ip_address: str | None,
        user_agent: str | None,
    ) -> ContractSignature:
        # 1. 幂等：同 idempotency_key 直接返回已有记录
        existing = await self.session.scalar(
            select(ContractSignature).where(
                ContractSignature.idempotency_key == payload.idempotency_key
            )
        )
        if existing:
            return existing

        # 2. 笔迹校验
        self.validate_strokes(payload)

        # 3. 加载合同与订单
        contract = await self.session.scalar(
            select(Contract).where(Contract.id == contract_id)
        )
        if not contract:
            raise ContractSignError("NOT_FOUND", "合同不存在", status_code=404)
        booking = await self.session.get(Booking, contract.booking_id)
        if not booking:
            raise ContractSignError("NOT_FOUND", "订单不存在", status_code=404)

        # 4. 越权校验：仅该合同租客可签
        if booking.tenant_id != tenant_user_id:
            raise ContractSignError("FORBIDDEN", "无权签署该合同", status_code=403)

        # 5. 版本校验
        if contract.version != payload.agreement_version:
            raise ContractSignError(
                "AGREEMENT_VERSION_MISMATCH",
                "合同版本已更新，请刷新后重新签署",
                status_code=409,
            )
        if contract.content_hash != payload.agreement_content_hash:
            raise ContractSignError(
                "AGREEMENT_VERSION_MISMATCH",
                "合同内容已变更，请刷新后重新签署",
                status_code=409,
            )

        # 6. 幂等：同合同同版本已签过
        dup = await self.session.scalar(
            select(ContractSignature).where(
                ContractSignature.agreement_id == contract_id,
                ContractSignature.agreement_version == payload.agreement_version,
            )
        )
        if dup:
            return dup

        # 7. 生成签名记录
        now = datetime.now(timezone.utc)
        signature_id = str(uuid.uuid4())
        stroke_data = self._serialize_strokes(payload)
        signature_hash = hashlib.sha256(
            f"{signature_id}:{payload.agreement_content_hash}:{now.isoformat()}".encode()
        ).hexdigest()
        object_key = f"signatures/{contract_id}/{signature_id}.json"
        self.storage.put_immutable(object_key, stroke_data.encode("utf-8"))

        record = ContractSignature(
            id=signature_id,
            agreement_id=contract_id,
            agreement_version=payload.agreement_version,
            agreement_content_hash=payload.agreement_content_hash,
            tenant_user_id=tenant_user_id,
            tenant_name=payload.tenant_name,
            signed_at=now,
            property_timezone="Asia/Shanghai",
            consent_text_version=payload.consent_text_version,
            signature_object_key=object_key,
            signature_hash=signature_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            idempotency_key=payload.idempotency_key,
        )
        self.session.add(record)

        # 8. 更新合同与订单状态
        contract.status = "signed"
        contract.signed_at = now
        contract.pdf_status = "pending"
        booking.status = BookingStatus.payment_pending
        booking.payment_expires_at = now + timedelta(hours=24)

        await self.session.commit()

        # 9. 异步生成 PDF（不阻塞响应）
        try:
            from app.services.order_notification_service import OrderNotificationService
            await OrderNotificationService(self.session).enqueue(
                "contract_signed", booking, contract=contract
            )
        except Exception:
            logger.exception("Failed to enqueue contract_signed notification")

        return record

    @staticmethod
    def _serialize_strokes(payload: ContractSignCreate) -> str:
        import json
        return json.dumps(
            [
                [{"x": p.x, "y": p.y, "pressure": p.pressure} for p in stroke]
                for stroke in payload.strokes
            ],
            ensure_ascii=False,
        )

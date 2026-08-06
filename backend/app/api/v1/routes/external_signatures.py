"""Dropbox Sign 模板配置、嵌入式签署与可信回调接口。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_landlord, require_tenant
from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract
from app.models.external_signature import (
    ExternalSignatureEvent,
    ExternalSignatureRequest,
    ExternalSignatureTemplateBinding,
)
from app.models.institute import Institute
from app.models.tenant import Tenant
from app.models.unit_type import UnitType
from app.models.user import User, UserRole
from app.schemas.external_signature import (
    EmbeddedSigningSession,
    EmbeddedSigningStart,
    TemplateBindingCreate,
    TemplateBindingRead,
    TemplateBindingUpdate,
)
from app.services.contract_service import ContractService
from app.services.dropbox_sign_service import DropboxSignError, DropboxSignService
from app.services.institute_access import can_manage_institute, managed_institute_filter

router = APIRouter()


@router.get("/configuration-status")
async def dropbox_sign_configuration_status(
    current_user: User = Depends(require_landlord),
) -> dict:
    """仅返回配置是否存在，绝不向前端暴露 API Key 或 Client ID。"""
    settings = DropboxSignService().settings
    return {
        "api_key_configured": bool(settings.dropbox_sign_api_key),
        "client_id_configured": bool(settings.dropbox_sign_client_id),
        "webhook_enabled": bool(settings.dropbox_sign_webhook_enabled),
        "test_mode": bool(settings.dropbox_sign_test_mode),
    }


def _as_string(value: object | None) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _mapped_fields(mapping: dict[str, str], values: dict[str, object | None]) -> dict[str, str]:
    """只输出已配置且有值的字段，禁止由客户端任意指定合同字段。"""
    return {
        template_field: _as_string(values.get(source))
        for template_field, source in mapping.items()
        if isinstance(template_field, str) and isinstance(source, str) and values.get(source) is not None
    }


async def _contract_institute_id(session: AsyncSession, contract: Contract) -> int | None:
    booking = await session.get(Booking, contract.booking_id)
    if not booking:
        return None
    if booking.institute_id:
        return booking.institute_id
    if not booking.unit_type_id:
        return None
    return await session.scalar(select(UnitType.institute_id).where(UnitType.id == booking.unit_type_id))


async def _active_binding(session: AsyncSession, institute_id: int) -> ExternalSignatureTemplateBinding | None:
    """公寓专用模板优先；不存在时才使用唯一的平台默认模板。"""
    binding = await session.scalar(
        select(ExternalSignatureTemplateBinding).where(
            ExternalSignatureTemplateBinding.institute_id == institute_id,
            ExternalSignatureTemplateBinding.provider == "dropbox_sign",
            ExternalSignatureTemplateBinding.is_active.is_(True),
        )
    )
    if binding:
        return binding
    return await session.scalar(
        select(ExternalSignatureTemplateBinding).where(
            ExternalSignatureTemplateBinding.institute_id.is_(None),
            ExternalSignatureTemplateBinding.is_default.is_(True),
            ExternalSignatureTemplateBinding.provider == "dropbox_sign",
            ExternalSignatureTemplateBinding.is_active.is_(True),
        )
    )


@router.get("/bindings", response_model=list[TemplateBindingRead])
async def list_template_bindings(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> list[ExternalSignatureTemplateBinding]:
    """返回当前 BM 可管理公寓的模板绑定；管理员可查看全部。"""
    stmt = select(ExternalSignatureTemplateBinding).order_by(ExternalSignatureTemplateBinding.created_at.desc())
    scope = managed_institute_filter(current_user)
    if scope is not None:
        stmt = stmt.join(Institute, Institute.id == ExternalSignatureTemplateBinding.institute_id).where(scope)
    return list((await session.scalars(stmt)).all())


@router.get("/templates")
async def list_dropbox_sign_templates(
    query: str | None = Query(default=None, max_length=120),
    current_user: User = Depends(require_landlord),
) -> dict:
    """代理读取 Dropbox Sign 模板，不把 API Key 暴露给浏览器。"""
    try:
        templates = await DropboxSignService().list_templates(query=query)
    except DropboxSignError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"items": templates}


@router.post("/bindings", response_model=TemplateBindingRead, status_code=status.HTTP_201_CREATED)
async def create_template_binding(
    payload: TemplateBindingCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> ExternalSignatureTemplateBinding:
    """配置服务器端认可的 Dropbox Sign 模板，字段映射不接受签署时临时覆盖。"""
    if payload.is_default and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="仅超级管理员可以配置平台默认模板")
    if payload.institute_id is None and not payload.is_default:
        raise HTTPException(status_code=422, detail="非默认模板必须关联公寓")
    if payload.institute_id is not None and not await can_manage_institute(session, current_user, payload.institute_id):
        raise HTTPException(status_code=403, detail="无权配置该公寓的签署模板")
    if payload.is_default:
        defaults = await session.scalars(
            select(ExternalSignatureTemplateBinding).where(
                ExternalSignatureTemplateBinding.provider == "dropbox_sign",
                ExternalSignatureTemplateBinding.is_default.is_(True),
            )
        )
        for item in defaults:
            item.is_default = False
    # 每个公寓的 Dropbox Sign 只保留一个当前活跃绑定，避免同一订单被随机选中多个模板。
    existing = await session.scalar(
        select(ExternalSignatureTemplateBinding).where(
            ExternalSignatureTemplateBinding.provider == "dropbox_sign",
            ExternalSignatureTemplateBinding.institute_id == payload.institute_id,
            ExternalSignatureTemplateBinding.is_active.is_(True),
        ).order_by(ExternalSignatureTemplateBinding.updated_at.desc())
    )
    if existing:
        existing.provider_template_id = payload.provider_template_id
        existing.signer_role = payload.signer_role
        existing.field_mapping = payload.field_mapping
        existing.is_default = payload.is_default
        await session.commit()
        await session.refresh(existing)
        return existing
    binding = ExternalSignatureTemplateBinding(provider="dropbox_sign", **payload.model_dump())
    session.add(binding)
    await session.commit()
    await session.refresh(binding)
    return binding


@router.put("/bindings/{binding_id}", response_model=TemplateBindingRead)
async def update_template_binding(
    binding_id: str,
    payload: TemplateBindingUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> ExternalSignatureTemplateBinding:
    binding = await session.get(ExternalSignatureTemplateBinding, binding_id)
    if not binding or binding.provider != "dropbox_sign":
        raise HTTPException(status_code=404, detail="Dropbox Sign 模板绑定不存在")
    if binding.institute_id is None:
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="仅超级管理员可管理平台默认模板")
    elif not await can_manage_institute(session, current_user, binding.institute_id):
        raise HTTPException(status_code=403, detail="无权管理该公寓的 Dropbox Sign 模板")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(binding, key, value)
    await session.commit()
    await session.refresh(binding)
    return binding


@router.delete("/bindings/{binding_id}", response_model=TemplateBindingRead)
async def deactivate_template_binding(
    binding_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> ExternalSignatureTemplateBinding:
    """软停用绑定，不删除历史签署请求的参照记录。"""
    binding = await update_template_binding(
        binding_id, TemplateBindingUpdate(is_active=False), session, current_user
    )
    return binding


@router.post("/{contract_id}/embedded-session", response_model=EmbeddedSigningSession)
async def start_embedded_signing(
    contract_id: str,
    payload: EmbeddedSigningStart,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> EmbeddedSigningSession:
    """租客确认后创建嵌入式签署会话；不经过人工审核。"""
    if current_user.role != UserRole.tenant:
        raise HTTPException(status_code=403, detail="仅合同租客可以发起签署")
    if not payload.electronic_signature_consent:
        raise HTTPException(status_code=422, detail="必须同意电子签署条款")
    contract = await session.get(Contract, contract_id)
    if not contract or contract.tenant_id != current_user.id:
        raise HTTPException(status_code=404, detail="合同不存在或无权签署")
    if contract.status == "signed":
        raise HTTPException(status_code=409, detail="合同已经签署")
    institute_id = await _contract_institute_id(session, contract)
    if institute_id is None:
        raise HTTPException(status_code=409, detail="合同未关联有效公寓，无法选择签署模板")
    binding = await _active_binding(session, institute_id)
    if not binding:
        raise HTTPException(status_code=409, detail="该公寓尚未配置可用的 Dropbox Sign 模板")

    existing = await session.scalar(
        select(ExternalSignatureRequest).where(
            ExternalSignatureRequest.contract_id == contract.id,
            ExternalSignatureRequest.status == "awaiting_signature",
            ExternalSignatureRequest.provider_signature_id.is_not(None),
        ).order_by(ExternalSignatureRequest.sent_at.desc())
    )
    service = DropboxSignService()
    try:
        if existing and existing.provider_signature_id:
            embedded = await service.get_embedded_sign_url(existing.provider_signature_id)
            return EmbeddedSigningSession(
                signature_request_id=existing.id,
                sign_url=embedded["sign_url"],
                expires_at=embedded.get("expires_at"),
                client_id=service.settings.dropbox_sign_client_id,
                test_mode=service.settings.dropbox_sign_test_mode,
            )

        booking = await session.get(Booking, contract.booking_id)
        tenant = await session.get(Tenant, booking.tenant_id) if booking and booking.tenant_id else None
        signer_email = (tenant.email if tenant else None) or current_user.email
        signer_name = " ".join(filter(None, [
            tenant.given_name_pinyin if tenant else None,
            tenant.surname_pinyin if tenant else None,
        ])) or (tenant.chinese_name if tenant else None) or current_user.username
        if not signer_email:
            raise HTTPException(status_code=422, detail="请先完善可接收签署邀请的邮箱")
        context = await ContractService(session).build_contract_context(booking.id)
        # 合同编号由已生成的合同快照决定，不能由客户端提供。
        context["agreement_number"] = contract.agreement_number
        values = {
            "tenant.chinese_name": tenant.chinese_name if tenant else None,
            "tenant.given_name": tenant.given_name_pinyin if tenant else None,
            "tenant.surname": tenant.surname_pinyin if tenant else None,
            "tenant.email": signer_email,
            "tenant.phone": tenant.phone if tenant else current_user.phone,
            "tenant.birth_date": tenant.birth_date if tenant else None,
            "booking.contract_start": booking.contract_start if booking else None,
            "booking.contract_end": booking.contract_end if booking else None,
            "booking.room_number": booking.room_number if booking else None,
            "contract.agreement_number": contract.agreement_number,
            # 平台标准合同字段均由后端真实订单数据计算。
            **context,
        }
        provider_request = await service.create_embedded_request(
            template_id=binding.provider_template_id,
            signer_role=binding.signer_role,
            signer_name=signer_name,
            signer_email=signer_email,
            custom_fields=_mapped_fields(binding.field_mapping, values),
            metadata={"contract_id": contract.id, "consent_text_version": payload.consent_text_version},
        )
        signature_id = provider_request["signatures"][0].get("signature_id")
        if not signature_id:
            raise DropboxSignError("Dropbox Sign 未返回租客签署标识")
        request_record = ExternalSignatureRequest(
            contract_id=contract.id,
            template_binding_id=binding.id,
            provider="dropbox_sign",
            provider_request_id=provider_request["signature_request_id"],
            provider_signature_id=signature_id,
            signer_name=signer_name,
            signer_email=signer_email,
            request_metadata={"consent_text_version": payload.consent_text_version},
        )
        session.add(request_record)
        await session.commit()
        embedded = await service.get_embedded_sign_url(signature_id)
        return EmbeddedSigningSession(
            signature_request_id=request_record.id,
            sign_url=embedded["sign_url"],
            expires_at=embedded.get("expires_at"),
            client_id=service.settings.dropbox_sign_client_id,
            test_mode=service.settings.dropbox_sign_test_mode,
        )
    except DropboxSignError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/webhook", include_in_schema=False)
async def dropbox_sign_webhook(request: Request, session: AsyncSession = Depends(get_db_session)) -> PlainTextResponse:
    """校验 Dropbox Sign 回调并幂等记录事件；供应商要求返回固定文本。"""
    service = DropboxSignService()
    if not service.settings.dropbox_sign_webhook_enabled:
        raise HTTPException(status_code=404, detail="Webhook 未启用")
    try:
        form = await request.form()
        raw = form.get("json")
        payload = json.loads(str(raw)) if raw else await request.json()
        event = payload.get("event", {})
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="无效的回调内容")
    if not isinstance(event, dict) or not service.verify_event(event):
        raise HTTPException(status_code=401, detail="无效的 Dropbox Sign 回调")

    provider_request_id = str(payload.get("signature_request", {}).get("signature_request_id", ""))
    event_type = str(event.get("event_type", "unknown"))
    event_id = str(event.get("event_hash") or hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest())
    if await session.scalar(select(ExternalSignatureEvent.id).where(
        ExternalSignatureEvent.provider == "dropbox_sign",
        ExternalSignatureEvent.provider_event_id == event_id,
    )):
        return PlainTextResponse("Hello API Event Received")
    signature_request = await session.scalar(select(ExternalSignatureRequest).where(
        ExternalSignatureRequest.provider == "dropbox_sign",
        ExternalSignatureRequest.provider_request_id == provider_request_id,
    ))
    audit_payload = {"signature_request_id": provider_request_id, "event_time": event.get("event_time")}
    audit_event = ExternalSignatureEvent(
        signature_request_id=signature_request.id if signature_request else None,
        provider="dropbox_sign", provider_event_id=event_id, event_type=event_type, payload=audit_payload,
        processed_at=datetime.now(timezone.utc),
    )
    session.add(audit_event)
    if signature_request:
        if event_type == "signature_request_all_signed":
            signature_request.status = "signed"
            signature_request.completed_at = datetime.now(timezone.utc)
            contract = await session.get(Contract, signature_request.contract_id)
            if contract:
                contract.status = "signed"
                contract.signed_at = signature_request.completed_at
                # 最终签署版必须从供应商下载到私有存储；失败不伪造成功文件，
                # 保留请求状态以便后续安全重试归档。
                try:
                    from app.services.private_object_storage import PrivateObjectStorage
                    signed_pdf = await service.download_signed_pdf(signature_request.provider_request_id)
                    object_key = f"contracts/{contract.id}/dropbox-signed.pdf"
                    PrivateObjectStorage().put(object_key, signed_pdf)
                    contract.file_path = object_key
                    contract.pdf_status = "ready"
                    signature_request.last_error = None
                except DropboxSignError as exc:
                    contract.pdf_status = "pending"
                    signature_request.last_error = str(exc)
                booking = await session.get(Booking, contract.booking_id)
                if booking and booking.status == BookingStatus.contract_ready:
                    booking.status = BookingStatus.contract_signed
        elif event_type in {"signature_request_canceled", "signature_request_declined"}:
            signature_request.status = "cancelled"
    await session.commit()
    return PlainTextResponse("Hello API Event Received")

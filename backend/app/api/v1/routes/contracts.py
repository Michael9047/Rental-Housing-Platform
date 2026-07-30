from datetime import datetime, timedelta, timezone

import jwt
import uuid
import logging
from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, get_db_session, require_tenant
from app.models.user import User, UserRole
from app.schemas.contract import ContractResponse, ContractSignCreate, ContractSignatureResponse, TenantContractDetail, TenantContractListResponse
from app.models.contract import Contract, ContractSignature
from app.services.booking_service import BookingService
from app.services.contract_service import ContractService

router = APIRouter()
logger = logging.getLogger(__name__)


def _can_access(current_user: User, booking) -> bool:
    return current_user.id in {booking.tenant_id, booking.landlord_id} or current_user.role == UserRole.admin


@router.post("/{booking_id}/generate", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def generate_contract(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    booking = await BookingService(session).get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id not in {booking.tenant_id, booking.landlord_id} and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    contract_service = ContractService(session)
    try:
        contract = await contract_service.generate_contract(booking)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return contract


@router.get("/by-booking/{booking_id}", response_model=ContractResponse)
async def get_contract_by_booking(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    booking = await BookingService(session).get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not _can_access(current_user, booking):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    contract = await ContractService(session).list_by_booking(booking_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    return contract


@router.get("/my", response_model=TenantContractListResponse)
async def list_my_contracts(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> TenantContractListResponse:
    from app.services.tenant_contract_service import TenantContractService
    items = await TenantContractService(session).list_for_tenant(current_user.id)
    return TenantContractListResponse(items=items, total=len(items))


@router.get("/my/{agreement_id}", response_model=TenantContractDetail)
async def get_my_contract(
    agreement_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> TenantContractDetail:
    from app.services.tenant_contract_service import TenantContractService
    try:
        return await TenantContractService(session).detail_for_tenant(agreement_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/my/{agreement_id}/signature")
async def get_my_contract_signature(
    agreement_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> Response:
    from app.services.private_object_storage import PrivateObjectStorage
    signature = await session.scalar(
        select(ContractSignature).join(Contract, Contract.id == ContractSignature.agreement_id)
        .where(ContractSignature.agreement_id == agreement_id, Contract.tenant_id == current_user.id)
    )
    if not signature:
        raise HTTPException(status_code=404, detail="合同不存在或无权查看")
    try:
        content = PrivateObjectStorage().get(signature.signature_object_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="签名文件暂不可用")
    return Response(content=content, media_type="image/svg+xml", headers={"Cache-Control":"private, no-store"})


@router.get("/my/{agreement_id}/signed-download-link")
async def create_my_signed_download_link(
    agreement_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> dict:
    """仅为合同租客创建短期签署版 PDF 下载链接。"""
    from app.core.config import get_settings

    contract = await session.scalar(
        select(Contract).where(
            Contract.id == agreement_id,
            Contract.tenant_id == current_user.id,
            Contract.status == "signed",
        )
    )
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在或无权下载")
    if not contract.file_path:
        return JSONResponse(
            status_code=202,
            content={
                "code": "PDF_GENERATION_PENDING",
                "message": "合同已签署，签署版 PDF 正在生成",
                "request_id": str(uuid.uuid4()),
            },
        )
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode(
        {"sub": contract.id, "purpose": "signed_contract_download", "exp": expires_at},
        settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
    )
    return {
        "url": f"/api/v1/contracts/signed-download/{token}",
        "expires_at": expires_at.isoformat(),
    }


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService(session).get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    if current_user.id not in {contract.tenant_id, booking := None} and current_user.role != UserRole.admin:
        booking = await BookingService(session).get(contract.booking_id)
        if booking and current_user.id not in {booking.tenant_id, booking.landlord_id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return contract


@router.post("/{contract_id}/sign", response_model=ContractSignatureResponse)
async def sign_contract(
    contract_id: str,
    payload_raw: dict,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> ContractSignatureResponse:
    from app.services.contract_signing_service import ContractSignError, ContractSigningService
    request_id=request.headers.get("x-request-id") or str(uuid.uuid4())
    try:
        try: payload=ContractSignCreate.model_validate(payload_raw)
        except ValidationError as exc:
            fields={str(item["loc"][-1]) for item in exc.errors()}
            code="CONSENT_REQUIRED" if fields & {"name_confirmed","electronic_signature_consent"} else "SIGNATURE_EMPTY" if "strokes" in fields else "INVALID_REQUEST"
            message={"CONSENT_REQUIRED":"请确认姓名并同意电子签名","SIGNATURE_EMPTY":"请先完成手写签名"}.get(code,"签署请求参数不正确")
            return JSONResponse(status_code=422,content={"code":code,"message":message,"request_id":request_id})
        return await ContractSigningService(session).sign(
            contract_id, current_user.id, payload,
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        )
    except ContractSignError as exc:
        return JSONResponse(status_code=exc.status_code,content={"code":exc.code,"message":exc.message,"request_id":request_id})
    except Exception:
        logger.exception("Contract signing failed request_id=%s contract_id=%s",request_id,contract_id)
        return JSONResponse(status_code=500,content={"code":"SIGNING_ERROR","message":"合同签署暂时不可用，请稍后重试","request_id":request_id})


@router.get("/{contract_id}/signed-download-link")
async def create_signed_download_link(
    contract_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.core.config import get_settings
    contract = await ContractService(session).get_contract(contract_id)
    if not contract or contract.status != "signed":
        raise HTTPException(status_code=404, detail="Signed contract not found")
    booking = await BookingService(session).get(contract.booking_id)
    if not booking or not _can_access(current_user, booking):
        raise HTTPException(status_code=403, detail="Access denied")
    if not contract.file_path:
        request_id = str(uuid.uuid4())
        return JSONResponse(
            status_code=202,
            content={
                "code": "PDF_GENERATION_PENDING",
                "message": "合同已签署，签署版PDF正在生成",
                "request_id": request_id,
            },
        )
    settings = get_settings(); expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode({"sub": contract.id, "purpose": "signed_contract_download", "exp": expires_at}, settings.auth_secret_key, algorithm=settings.auth_algorithm)
    return {"url": f"/api/v1/contracts/signed-download/{token}", "expires_at": expires_at.isoformat()}


@router.get("/signed-download/{token}")
async def download_signed_contract(token: str, session: AsyncSession = Depends(get_db_session)) -> Response:
    from app.core.config import get_settings
    from app.services.private_object_storage import PrivateObjectStorage
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])
        if claims.get("purpose") != "signed_contract_download": raise ValueError("purpose")
    except Exception:
        raise HTTPException(status_code=401, detail="Download link is invalid or expired")
    contract = await ContractService(session).get_contract(str(claims.get("sub")))
    if not contract or contract.status != "signed" or not contract.file_path:
        raise HTTPException(status_code=404, detail="Signed contract not found")
    return Response(content=PrivateObjectStorage().get(contract.file_path), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{contract.agreement_number}.pdf"'})


@router.get("/{contract_id}/download")
async def download_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    contract = await ContractService(session).get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    booking = await BookingService(session).get(contract.booking_id)
    if booking and current_user.id not in {booking.tenant_id, booking.landlord_id} and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    from app.services.contract_pdf_service import ContractPdfService
    from app.services.private_object_storage import PrivateObjectStorage
    if contract.status == "signed" and not contract.file_path:
        return JSONResponse(
            status_code=202,
            content={
                "code": "PDF_GENERATION_PENDING",
                "message": "合同已签署，签署版PDF正在生成",
                "request_id": str(uuid.uuid4()),
            },
        )
    pdf = PrivateObjectStorage().get(contract.file_path) if contract.status == "signed" else await ContractPdfService().generate(contract)
    filename = f"{contract.agreement_number or contract.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

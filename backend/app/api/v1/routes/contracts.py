from datetime import datetime, timedelta, timezone

import jwt
import uuid
import logging
from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select

from app.api.deps import get_current_user, get_db_session, require_tenant
from app.models.user import User, UserRole
from app.schemas.contract import ContractResponse, ContractSignCreate, ContractSignatureResponse, TenantContractDetail, TenantContractListResponse
from app.models.contract import Contract, ContractSignature
from app.services.booking_service import BookingService
from app.services.contract_service import ContractService

router = APIRouter()
logger = logging.getLogger(__name__)


def _can_access(current_user: User, booking) -> bool:
    result = current_user.id in {booking.user_id, booking.bm_id} or current_user.role == UserRole.admin
    logger.info("_can_access user=%s(%s) booking=%s user_id=%s bm_id=%s role=%s => %s",
        current_user.id, current_user.username, booking.id,
        booking.user_id, booking.bm_id, current_user.role.value, result)
    return result


async def _can_access_booking(session: AsyncSession, current_user: User, booking) -> bool:
    """兼容历史订单未写入 bm_id 的情况，按公寓归属判断 BM 权限。"""
    if _can_access(current_user, booking):
        return True
    if current_user.role != UserRole.landlord or not booking.institute_id:
        return False
    from app.services.institute_access import can_manage_institute
    return await can_manage_institute(session, current_user, booking.institute_id)


@router.post("/{booking_id}/generate", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def generate_contract(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    from sqlalchemy.orm import selectinload
    from app.models.booking import Booking
    from app.models.property import Room
    from app.models.unit_type import UnitType
    booking = (await session.scalars(
        select(Booking).where(Booking.id == booking_id).options(
            selectinload(Booking.property).selectinload(Room.unit_type).selectinload(UnitType.institute),
            selectinload(Booking.tenant),
        )
    )).unique().first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if not _can_access(current_user, booking):
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied [by-booking]")
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


# ═══════════════════════════════════════════════════════════════
# 合同模板管理
# ═══════════════════════════════════════════════════════════════

from app.schemas.contract_template import TemplateCreate, TemplateUpdate, TemplateRead, TemplateListResponse
from app.models.contract_template import ContractTemplate
from app.services.private_object_storage import PrivateObjectStorage
from fastapi import UploadFile, File, Form


@router.post("/templates", response_model=TemplateRead, status_code=201)
async def upload_template(
    name: str = Form(...),
    institute_id: int = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """BM 上传合同 PDF 模板 — 绑定到指定公寓"""
    if current_user.role not in (UserRole.landlord, UserRole.admin):
        raise HTTPException(403, "仅房东可上传模板")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    pdf_bytes = await file.read()
    tpl_id = str(uuid.uuid4())
    storage_key = f"contract_templates/{current_user.id}/{tpl_id}.pdf"
    PrivateObjectStorage().put(storage_key, pdf_bytes)

    tpl = ContractTemplate(
        id=tpl_id, bm_id=current_user.id, institute_id=institute_id,
        name=name.strip(), file_path=storage_key, field_positions={},
    )
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    return tpl


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """BM 查看自己的模板列表"""
    stmt = (
        select(ContractTemplate)
        .where(ContractTemplate.bm_id == current_user.id)
        .order_by(ContractTemplate.created_at.desc())
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    return TemplateListResponse(items=items, total=len(items))


@router.get("/templates/{template_id}", response_model=TemplateRead)
async def get_template(
    template_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    tpl = await session.get(ContractTemplate, template_id)
    if not tpl or tpl.bm_id != current_user.id:
        raise HTTPException(404, "模板不存在")
    return tpl


@router.get("/templates/{template_id}/file")
async def download_template_file(
    template_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """下载模板 PDF 文件"""
    tpl = await session.get(ContractTemplate, template_id)
    if not tpl or tpl.bm_id != current_user.id:
        raise HTTPException(404, "模板不存在")
    try:
        pdf_bytes = PrivateObjectStorage().get(tpl.file_path)
    except FileNotFoundError:
        raise HTTPException(404, "模板文件不存在")
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.put("/templates/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """更新模板名称或保存字段坐标"""
    tpl = await session.get(ContractTemplate, template_id)
    if not tpl or tpl.bm_id != current_user.id:
        raise HTTPException(404, "模板不存在")
    update = data.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(tpl, k, v)
    await session.commit()
    await session.refresh(tpl)
    return tpl


@router.delete("/templates/{template_id}", status_code=200)
async def delete_template(
    template_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    tpl = await session.get(ContractTemplate, template_id)
    if not tpl or tpl.bm_id != current_user.id:
        raise HTTPException(404, "模板不存在")
    try:
        PrivateObjectStorage().delete(tpl.file_path)
    except Exception:
        pass
    await session.delete(tpl)
    await session.commit()
    return {"ok": True}


# ── 房东合约列表 ──

from pydantic import BaseModel as _PydanticBaseModel

class _LandlordContractItem(_PydanticBaseModel):
    id: str
    agreement_number: str | None = None
    tenant_name: str | None = None
    unit_type_name: str | None = None
    status: str | None = None
    signed_at: datetime | None = None
    generated_at: datetime | None = None


class _LandlordContractList(_PydanticBaseModel):
    items: list[_LandlordContractItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    status_counts: dict[str, int]


@router.get("/landlord", response_model=_LandlordContractList)
async def list_landlord_contracts(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    page: int = 1, page_size: int = 20,
):
    """房东查看自己公寓下的所有合同"""
    from sqlalchemy.orm import selectinload
    from app.models.booking import Booking
    from app.models.institute import Institute
    from app.services.institute_access import managed_institute_filter

    booking_stmt = select(Booking.id).join(
        Institute, Booking.institute_id == Institute.id, isouter=True
    )
    scope = managed_institute_filter(current_user)
    if scope is not None:
        booking_stmt = booking_stmt.where(or_(Booking.bm_id == current_user.id, scope))
    booking_result = await session.execute(booking_stmt)
    booking_ids = [r[0] for r in booking_result.all()]

    if not booking_ids:
        return _LandlordContractList(items=[], total=0, page=page, page_size=page_size, total_pages=0, status_counts={})

    count_stmt = select(func.count(Contract.id)).where(Contract.booking_id.in_(booking_ids))
    total = (await session.scalar(count_stmt)) or 0
    status_rows = (await session.execute(
        select(Contract.status, func.count(Contract.id))
        .where(Contract.booking_id.in_(booking_ids))
        .group_by(Contract.status)
    )).all()
    status_counts = {str(contract_status): count for contract_status, count in status_rows}

    stmt = (
        select(Contract)
        .where(Contract.booking_id.in_(booking_ids))
        .options(
            selectinload(Contract.tenant),
            selectinload(Contract.booking).selectinload(Booking.unit_type),
        )
        .order_by(Contract.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    result = await session.execute(stmt)
    contracts = result.scalars().unique().all()

    items = []
    for c in contracts:
        tenant = c.tenant
        unit_type = c.booking.unit_type if c.booking else None
        items.append(_LandlordContractItem(
            id=c.id, agreement_number=c.agreement_number,
            tenant_name=tenant.username if tenant else None,
            unit_type_name=unit_type.name if unit_type else None,
            status=str(c.status) if c.status else None,
            signed_at=c.signed_at, generated_at=c.generated_at or c.created_at,
        ))

    return _LandlordContractList(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
        status_counts=status_counts,
    )


@router.get("/landlord/{agreement_id}", response_model=TenantContractDetail)
async def get_landlord_contract_detail(
    agreement_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> TenantContractDetail:
    """BM 复用租客合同详情数据结构，同时按公寓管理范围鉴权。"""
    contract = await ContractService(session).get_contract(agreement_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    booking = await BookingService(session).get(contract.booking_id)
    if not booking or not await _can_access_booking(session, current_user, booking):
        raise HTTPException(status_code=403, detail="Access denied")
    from app.services.tenant_contract_service import TenantContractService
    try:
        return await TenantContractService(session).detail_for_tenant(agreement_id, contract.tenant_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    contract = await ContractService(session).get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    booking = await BookingService(session).get(contract.booking_id)
    if not booking or not await _can_access_booking(session, current_user, booking):
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
    if not booking or not await _can_access_booking(session, current_user, booking):
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
    if not booking or not await _can_access_booking(session, current_user, booking):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    from app.services.contract_pdf_render_service import ContractPdfRenderService, ContractRenderError
    if contract.status == "signed" and not contract.file_path:
        return JSONResponse(
            status_code=202,
            content={
                "code": "PDF_GENERATION_PENDING",
                "message": "合同已签署，签署版PDF正在生成",
                "request_id": str(uuid.uuid4()),
            },
        )
    # 优先返回已渲染的 PDF（由 BM 确认房号时生成），否则回退到在线生成
    try:
        pdf = await ContractPdfRenderService(session).render_current_contract(contract)
    except ContractRenderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    filename = f"{contract.agreement_number or contract.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



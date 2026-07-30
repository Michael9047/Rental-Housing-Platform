"""户型路由 — 三层架构中间层"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.schemas.unit_type import (
    UnitTypeCreate, UnitTypeUpdate, UnitTypeRead, UnitTypeListResponse,
)
from app.services.unit_type_service import UnitTypeService

router = APIRouter(tags=["unit-types"])


def _safe_enum(val):
    if val is None:
        return None
    return val.value if hasattr(val, 'value') else val


def _to_read(ut) -> UnitTypeRead:
    images = []
    for img in sorted(ut.images or [], key=lambda x: x.sort_order):
        images.append({
            "id": img.id, "filename": img.filename, "original_name": img.original_name,
            "sort_order": img.sort_order, "is_primary": img.is_primary,
        })
    return UnitTypeRead(
        id=ut.id, business_id=ut.business_id, uuid=ut.uuid,
        institute_id=ut.institute_id,
        institute_name=getattr(ut, '_institute_name', None) or (ut.institute.name if ut.institute else None),
        institute_business_id=getattr(ut, '_institute_business_id', None) or (ut.institute.business_id if ut.institute else None),
        name=ut.name, bedrooms=ut.bedrooms, bathrooms=ut.bathrooms, hall_count=ut.hall_count,
        area_sqm=ut.area_sqm, base_rent=ut.base_rent,
        deposit_amount=ut.deposit_amount, deposit_type=_safe_enum(ut.deposit_type),
        lease_start=ut.lease_start, lease_start_date=ut.lease_start_date,
        lease_end=ut.lease_end, lease_end_date=ut.lease_end_date,
        rental_requirements=ut.rental_requirements,
        currency=ut.currency, special_offer=ut.special_offer,
        floor_pricing=ut.floor_pricing, amenities=ut.amenities,
        description=ut.description, available_from=ut.available_from,
        min_stay_months=ut.min_stay_months, status=_safe_enum(ut.status),
        room_count=getattr(ut, '_room_count', 0),
        images=images,
        deleted_at=ut.deleted_at, created_at=ut.created_at, updated_at=ut.updated_at,
    )


@router.post("", response_model=UnitTypeRead, status_code=201)
async def create_unit_type(data: UnitTypeCreate, session: AsyncSession = Depends(get_db_session), _current_user: User = Depends(require_landlord)):
    ut = await UnitTypeService(session).create(data)
    return _to_read(ut)


@router.get("", response_model=UnitTypeListResponse)
async def list_unit_types(session: AsyncSession = Depends(get_db_session), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=500), institute_id: int | None = Query(default=None)):
    skip = (page - 1) * page_size
    result = await UnitTypeService(session).list(skip=skip, limit=page_size, institute_id=institute_id)
    items = [_to_read(ut) for ut in result["items"]]
    return UnitTypeListResponse(items=items, total=result["total"], page=result["page"], page_size=result["page_size"], total_pages=result["total_pages"])


@router.get("/recycle-bin", response_model=UnitTypeListResponse)
async def list_deleted_unit_types(session: AsyncSession = Depends(get_db_session), _current_user: User = Depends(require_landlord), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=2000), institute_id: int | None = Query(default=None)):
    skip = (page - 1) * page_size
    result = await UnitTypeService(session).list_deleted(skip=skip, limit=page_size, institute_id=institute_id)
    items = [_to_read(ut) for ut in result["items"]]
    return UnitTypeListResponse(items=items, total=result["total"], page=result["page"], page_size=result["page_size"], total_pages=result["total_pages"])


@router.get("/{unit_type_id}", response_model=UnitTypeRead)
async def get_unit_type(unit_type_id: int, session: AsyncSession = Depends(get_db_session)):
    ut = await UnitTypeService(session).get(unit_type_id)
    if not ut: raise HTTPException(404, "户型不存在")
    return _to_read(ut)


@router.patch("/{unit_type_id}", response_model=UnitTypeRead)
async def update_unit_type(unit_type_id: int, data: UnitTypeUpdate, session: AsyncSession = Depends(get_db_session), _current_user: User = Depends(require_landlord)):
    ut = await UnitTypeService(session).update(unit_type_id, data)
    if not ut: raise HTTPException(404, "户型不存在")
    return _to_read(ut)


@router.delete("/{unit_type_id}", status_code=204)
async def delete_unit_type(unit_type_id: int, session: AsyncSession = Depends(get_db_session), _current_user: User = Depends(require_landlord)):
    ok = await UnitTypeService(session).delete(unit_type_id)
    if not ok: raise HTTPException(404, "户型不存在")


@router.post("/{unit_type_id}/restore", response_model=UnitTypeRead)
async def restore_unit_type(unit_type_id: int, session: AsyncSession = Depends(get_db_session), _current_user: User = Depends(require_landlord)):
    ut = await UnitTypeService(session).restore(unit_type_id)
    if not ut: raise HTTPException(404, "户型不存在或未被删除")
    return _to_read(ut)


@router.delete("/{unit_type_id}/hard", status_code=204)
async def hard_delete_unit_type(unit_type_id: int, session: AsyncSession = Depends(get_db_session), _current_user: User = Depends(require_landlord)):
    from app.models.property import Room
    ut = await UnitTypeService(session).get(unit_type_id)
    if not ut: raise HTTPException(404, "户型不存在")
    if ut.deleted_at is None: raise HTTPException(400, "请先将户型移入回收站再硬删除")
    room_result = await session.execute(select(Room).where(Room.unit_type_id == unit_type_id))
    for r in room_result.scalars().all(): await session.delete(r)
    ut_name = ut.name
    await session.delete(ut)
    await session.commit()
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="硬删除户型", resource_type="unit_type", resource_id=unit_type_id, details={"户型名": ut_name})
        session.add(log); await session.commit()
    except Exception: pass


@router.post("/{unit_type_id}/copy", response_model=UnitTypeRead, status_code=201)
async def copy_unit_type(unit_type_id: int, session: AsyncSession = Depends(get_db_session), _current_user: User = Depends(require_landlord)):
    original = await UnitTypeService(session).get(unit_type_id)
    if not original: raise HTTPException(404, "户型不存在")
    import copy, uuid as _uuid
    from app.core.business_id import generate_business_id
    biz_id = await generate_business_id(session, "unit_type")
    ut = UnitTypeService(session)
    data = UnitTypeCreate(
        institute_id=original.institute_id, name=f"{original.name} (副本)",
        bedrooms=original.bedrooms, bathrooms=original.bathrooms, hall_count=original.hall_count,
        area_sqm=original.area_sqm, base_rent=original.base_rent,
        deposit_amount=original.deposit_amount, deposit_type=_safe_enum(original.deposit_type),
        lease_start=original.lease_start, lease_start_date=original.lease_start_date,
        lease_end=original.lease_end, lease_end_date=original.lease_end_date,
        currency=original.currency, special_offer=original.special_offer,
        floor_pricing=copy.deepcopy(original.floor_pricing) if original.floor_pricing else None,
        amenities=list(original.amenities) if original.amenities else None,
        description=original.description, available_from=original.available_from,
        min_stay_months=original.min_stay_months, status=_safe_enum(original.status),
    )
    new_ut = await UnitTypeService(session).create(data)
    return _to_read(new_ut)

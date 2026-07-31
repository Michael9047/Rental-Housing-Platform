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


<<<<<<< HEAD
=======
# ═══ 注意：不带路径参数的路由必须放在带路径参数的路由之前 ═══

@router.post("", response_model=UnitTypeRead, status_code=201)
async def create_unit_type(
    data: UnitTypeCreate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    ut = await UnitTypeService(session).create(data)
    return _to_read(ut)


@router.get("", response_model=UnitTypeListResponse)
async def list_unit_types(
    session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    institute_id: int | None = Query(default=None, description="筛选公寓"),
):
    skip = (page - 1) * page_size
    result = await UnitTypeService(session).list(
        skip=skip, limit=page_size, institute_id=institute_id
    )
    items = [_to_read(ut) for ut in result["items"]]
    return UnitTypeListResponse(
        items=items, total=result["total"], page=result["page"],
        page_size=result["page_size"], total_pages=result["total_pages"],
    )


@router.get("/search")
async def search_unit_types(
    session: AsyncSession = Depends(get_db_session),
    q: str | None = Query(default=None, description="关键词搜索"),
    country: str | None = Query(default=None),
    city: str | None = Query(default=None),
    district: str | None = Query(default=None),
    institute_id: int | None = Query(default=None),
    price_min: int | None = Query(default=None),
    price_max: int | None = Query(default=None),
    bedrooms: int | None = Query(default=None),
    bathrooms: int | None = Query(default=None),
    property_type: str | None = Query(default=None),
    amenities: list[str] | None = Query(default=None),
    area_min: float | None = Query(default=None),
    area_max: float | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    status: str | None = Query(default=None),
):
    """搜索户型 — 兼容前端旧 /properties/search 调用"""
    from app.services.property_service import PropertyService
    results = await PropertyService(session).search(
        query=q, country=country, city=city, district=district,
        institute_id=institute_id, price_min=price_min, price_max=price_max,
        bedrooms=bedrooms, bathrooms=bathrooms, property_type=property_type,
        amenities=amenities, area_min=area_min, area_max=area_max,
        sort_by=sort_by, limit=limit, status=status,
    )
    items = []
    for unit_type, similarity in results:
        d = _to_read(unit_type)
        if similarity is not None:
            d["similarity"] = float(similarity)
        items.append(d)
    return items


@router.get("/recycle-bin", response_model=UnitTypeListResponse)
async def list_deleted_unit_types(
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=2000),
    institute_id: int | None = Query(default=None),
):
    """已删除户型回收站"""
    skip = (page - 1) * page_size
    result = await UnitTypeService(session).list_deleted(skip=skip, limit=page_size, institute_id=institute_id)
    items = [_to_read(ut) for ut in result["items"]]
    return UnitTypeListResponse(
        items=items, total=result["total"], page=result["page"],
        page_size=result["page_size"], total_pages=result["total_pages"],
    )


@router.get("/{unit_type_id}", response_model=UnitTypeRead)
async def get_unit_type(
    unit_type_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    ut = await UnitTypeService(session).get(unit_type_id)
    if not ut:
        from fastapi import HTTPException
        raise HTTPException(404, "户型不存在")
    return _to_read(ut)


@router.patch("/{unit_type_id}", response_model=UnitTypeRead)
async def update_unit_type(
    unit_type_id: int,
    data: UnitTypeUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    ut = await UnitTypeService(session).update(unit_type_id, data)
    if not ut:
        from fastapi import HTTPException
        raise HTTPException(404, "户型不存在")
    return _to_read(ut)


@router.delete("/{unit_type_id}", status_code=204)
async def delete_unit_type(
    unit_type_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """软删除户型 — 移入回收站"""
    ok = await UnitTypeService(session).delete(unit_type_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(404, "户型不存在")


@router.post("/{unit_type_id}/restore", response_model=UnitTypeRead)
async def restore_unit_type(
    unit_type_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """从回收站恢复户型"""
    ut = await UnitTypeService(session).restore(unit_type_id)
    if not ut:
        from fastapi import HTTPException
        raise HTTPException(404, "户型不存在或未被删除")
    return _to_read(ut)


@router.delete("/{unit_type_id}/hard", status_code=204)
async def hard_delete_unit_type(
    unit_type_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """硬删除户型及所有下属房间（不可恢复）"""
    from app.models._compat import Room
    ut = await UnitTypeService(session).get(unit_type_id)
    if not ut:
        from fastapi import HTTPException
        raise HTTPException(404, "户型不存在")
    if ut.deleted_at is None:
        from fastapi import HTTPException
        raise HTTPException(400, "请先将户型移入回收站再硬删除")
    # 硬删除下属房间
    room_result = await session.execute(
        select(Room).where(Room.unit_type_id == unit_type_id)
    )
    for r in room_result.scalars().all():
        await session.delete(r)
    # 硬删除户型
    ut_name = ut.name
    await session.delete(ut)
    await session.commit()
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="硬删除户型", resource_type="unit_type", resource_id=unit_type_id,
                       details={"户型名": ut_name})
        session.add(log); await session.commit()
    except Exception: pass


@router.post("/{unit_type_id}/copy", response_model=UnitTypeRead, status_code=201)
async def copy_unit_type(
    unit_type_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """复制户型 — 除名称外全部参数一致"""
    original = await UnitTypeService(session).get(unit_type_id)
    if not original:
        from fastapi import HTTPException
        raise HTTPException(404, "户型不存在")
    from app.schemas.unit_type import UnitTypeCreate
    import copy
    data = UnitTypeCreate(
        institute_id=original.institute_id,
        name=f"{original.name} (副本)",
        bedrooms=original.bedrooms,
        bathrooms=original.bathrooms,
        hall_count=original.hall_count,
        area_sqm=original.area_sqm,
        base_rent=original.base_rent,
        deposit_amount=original.deposit_amount,
        deposit_type=original.deposit_type.value if hasattr(original.deposit_type, 'value') else original.deposit_type,
        lease_start=original.lease_start,
        lease_end=original.lease_end,
        currency=original.currency,
        special_offer=original.special_offer,
        floor_pricing=copy.deepcopy(original.floor_pricing) if original.floor_pricing else None,
        amenities=list(original.amenities) if original.amenities else None,
        image_urls=list(original.image_urls) if original.image_urls else None,
        description=original.description,
        available_from=original.available_from,
        min_stay_months=original.min_stay_months,
        status=_safe_enum(original.status),
    )
    ut = await UnitTypeService(session).create(data)
    return _to_read(ut)


>>>>>>> merge/pr33-pr35
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

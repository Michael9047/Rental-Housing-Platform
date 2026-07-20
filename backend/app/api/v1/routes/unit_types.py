"""户型路由 — 三层架构中间层"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.schemas.unit_type import (
    UnitTypeCreate, UnitTypeUpdate, UnitTypeRead, UnitTypeListResponse,
)
from app.services.unit_type_service import UnitTypeService

router = APIRouter(tags=["unit-types"])


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
    ok = await UnitTypeService(session).delete(unit_type_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(404, "户型不存在")


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


def _safe_enum(val):
    """安全获取枚举值，兼容 DB 返回的字符串"""
    if val is None:
        return None
    return val.value if hasattr(val, 'value') else val


def _safe_institute_name(ut) -> str | None:
    """安全获取公寓名称，优先使用预加载的 _institute_name"""
    if hasattr(ut, "_institute_name") and ut._institute_name:
        return ut._institute_name
    try:
        return ut.institute.name if ut.institute else None
    except Exception:
        return None


def _safe_institute_biz(ut) -> str | None:
    """安全获取公寓业务编号"""
    if hasattr(ut, "_institute_business_id") and ut._institute_business_id:
        return ut._institute_business_id
    try:
        return ut.institute.business_id if ut.institute else None
    except Exception:
        return None


def _to_read(ut) -> UnitTypeRead:
    return UnitTypeRead(
        id=ut.id,
        institute_id=ut.institute_id,
        institute_name=_safe_institute_name(ut),
        institute_business_id=_safe_institute_biz(ut),
        name=ut.name,
        bedrooms=ut.bedrooms,
        bathrooms=ut.bathrooms,
        hall_count=ut.hall_count,
        area_sqm=ut.area_sqm,
        base_rent=ut.base_rent,
        deposit_amount=ut.deposit_amount,
        deposit_type=_safe_enum(ut.deposit_type),
        floor_pricing=ut.floor_pricing,
        amenities=ut.amenities,
        image_urls=ut.image_urls,
        description=ut.description,
        available_from=ut.available_from,
        min_stay_months=ut.min_stay_months,
        status=_safe_enum(ut.status),
        room_count=getattr(ut, "_room_count", 0),
        created_at=ut.created_at,
        updated_at=ut.updated_at,
    )

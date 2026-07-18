from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.schemas.property import PropertyCreate, PropertyListResponse, PropertyRead, PropertySearchResult, PropertyUpdate
from app.schemas.property_image import PropertyImageRead
from app.services.property_service import PropertyService
from app.services.user_service import UserService
from app.models.property import Property
from app.tasks.poi_tasks import generate_map_pois_for_property

router = APIRouter()


@router.post("", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_in: PropertyCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> PropertyRead:
    landlord = await UserService(session).get(property_in.landlord_id)
    if not landlord:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                           detail="landlord_id does not reference an existing user")
    if current_user.role.value != "admin" and property_in.landlord_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                           detail="Landlords can only create properties for themselves")
    prop = await PropertyService(session).create(property_in)
    # 异步生成地图 POI（Celery 任务，不阻塞响应）
    generate_map_pois_for_property.delay(prop.id)
    return prop


@router.get("/search", response_model=list[PropertySearchResult])
async def search_properties(
    q: str | None = Query(default=None),
    district: str | None = Query(default=None),
    price_min: Decimal | None = Query(default=None, ge=0),
    price_max: Decimal | None = Query(default=None, ge=0),
    bedrooms: int | None = Query(default=None, ge=0),
    property_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    institute_id: int | None = Query(default=None, ge=1),
    amenities: list[str] | None = Query(default=None),
    available_from: str | None = Query(default=None),
    room_type: str | None = Query(default=None),
    min_lease_months: int | None = Query(default=None, ge=0),
    max_lease_months: int | None = Query(default=None, ge=0),
    sort_by: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[PropertySearchResult]:
    results = await PropertyService(session).search(
        query=q, district=district, price_min=price_min,
        price_max=price_max, bedrooms=bedrooms,
        property_type=property_type, limit=limit,
        institute_id=institute_id,
        amenities=amenities,
        available_from=available_from,
        room_type=room_type,
        min_lease_months=min_lease_months,
        max_lease_months=max_lease_months,
        sort_by=sort_by,
    )
    return [
        PropertySearchResult(
            id=prop.id, landlord_id=prop.landlord_id,
            title=prop.title, description=prop.description,
            address=prop.address, district=prop.district,
            price_monthly=prop.price_monthly,
            area_sqm=prop.area_sqm, bedrooms=prop.bedrooms, bathrooms=prop.bathrooms,
            property_type=prop.property_type, status=prop.status,
            latitude=prop.latitude, longitude=prop.longitude,
            created_at=prop.created_at, updated_at=prop.updated_at,
            images=[PropertyImageRead(id=img.id, property_id=img.property_id,
                     filename=img.filename, original_name=img.original_name,
                     mime_type=img.mime_type, file_size=img.file_size,
                     sort_order=img.sort_order, is_primary=img.is_primary,
                     created_at=img.created_at) for img in (prop.images or [])],
            institute_id=prop.institute_id,
            institute_name=getattr(prop, 'institute_name', None),
            similarity=sim,
        )
        for prop, sim in results
    ]


@router.get("", response_model=PropertyListResponse)
async def list_properties(
    session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    district: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    landlord_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    property_type: str | None = Query(default=None),
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    institute_id: int | None = Query(default=None),
) -> PropertyListResponse:
    skip = (page - 1) * page_size
    result = await PropertyService(session).list(
        skip=skip, limit=page_size,
        district=district, status=status_filter,
        landlord_id=landlord_id, keyword=keyword,
        property_type=property_type,
        price_min=price_min, price_max=price_max,
        institute_id=institute_id,
    )
    return PropertyListResponse(**result)


# ── 回收站 ──
@router.get("/recycle-bin", response_model=PropertyListResponse)
async def list_deleted_properties(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    landlord_id: int | None = Query(default=None),
) -> PropertyListResponse:
    skip = (page - 1) * page_size
    result = await PropertyService(session).list(
        skip=skip, limit=page_size,
        landlord_id=landlord_id or current_user.id,
        include_deleted=True,
    )
    # 只返回已删除的
    deleted_items = [p for p in result["items"] if p.deleted_at is not None]
    total = len(deleted_items)
    return PropertyListResponse(
        items=deleted_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/audit/recent")
async def list_recent_property_audit(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """获取当前房东所有房源的最新操作记录（按时间倒序）

    用于发布房源首页下方的修改记录展示。
    管理员可看全部；普通房东仅看自己的房源记录。
    """
    from sqlalchemy import select, or_
    from app.models.audit_log import AuditLog
    from app.models.institute import Institute
    from app.models.user import User as UserModel

    base_select = (
        select(
            AuditLog,
            Property.title.label("property_title"),
            Property.address.label("property_address"),
            Institute.name.label("institute_name"),
            UserModel.username.label("username"),
        )
        .outerjoin(Property, AuditLog.resource_id == Property.id)
        .outerjoin(Institute, Property.institute_id == Institute.id)
        .outerjoin(UserModel, AuditLog.user_id == UserModel.id)
    )

    if current_user.role.value == "admin":
        stmt = (
            base_select
            .where(AuditLog.resource_type == "property")
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    else:
        prop_ids_stmt = select(Property.id).where(Property.landlord_id == current_user.id)
        stmt = (
            base_select
            .where(
                AuditLog.resource_type == "property",
                or_(
                    AuditLog.resource_id.in_(prop_ids_stmt),
                    AuditLog.user_id == current_user.id,
                ),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )

    result = await session.execute(stmt)
    rows = result.all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "username": username,
            "action": log.action,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
            # 优先取 JOIN 的实时数据；若房源已删除则回退到审计日志 details 中的快照
            "property_title": property_title or (log.details or {}).get("property_title") or (log.details or {}).get("title"),
            "property_address": property_address or (log.details or {}).get("property_address"),
            "institute_name": institute_name or (log.details or {}).get("institute_name"),
        }
        for log, property_title, property_address, institute_name, username in rows
    ]


# ── 批量操作（必须在 /{property_id} 路由之前注册，否则会被拦截）──
@router.post("/batch/status")
async def batch_update_status(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    ids = body.get("ids", [])
    new_status = body.get("status", "offline")
    if not ids:
        raise HTTPException(status_code=400, detail="ids is required")
    return await PropertyService(session).batch_update_status(ids, new_status, current_user.id)


@router.post("/batch/delete")
async def batch_delete_properties(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids is required")
    return await PropertyService(session).batch_delete(ids, current_user.id)


@router.post("/batch/restore")
async def batch_restore_properties(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    ids = body.get('ids', [])
    if not ids:
        raise HTTPException(status_code=400, detail='ids is required')
    return await PropertyService(session).batch_restore(ids, current_user.id)

@router.post("/batch/hard-delete")
async def batch_hard_delete_properties(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    ids = body.get('ids', [])
    if not ids:
        raise HTTPException(status_code=400, detail='ids is required')
    return await PropertyService(session).batch_hard_delete(ids, current_user.id)


# ── 回收站操作 ──
@router.delete("/{property_id}/hard", status_code=204)
async def hard_delete_property(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> None:
    ps = PropertyService(session)
    deleted = await ps.hard_delete(property_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Property not found in recycle bin")


@router.post("/{property_id}/restore", response_model=PropertyRead)
async def restore_property(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> PropertyRead:
    prop = await PropertyService(session).restore(property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found in recycle bin")
    return prop


@router.post("/{property_id}/revert/{audit_log_id}")
async def revert_property_audit(
    property_id: int,
    audit_log_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """撤销某条审计日志对应的房源操作

    支持撤销: property_create, property_update, property_delete, property_restore
    不支持: property_hard_delete, property_batch_*
    """
    ps = PropertyService(session)
    try:
        result = await ps.revert_audit(property_id, audit_log_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.delete("/audit/{audit_log_id}", status_code=204)
async def delete_audit_log(
    audit_log_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> None:
    """删除单条审计日志（仅限自己的房源）"""
    from app.services.audit_service import AuditService
    audit_svc = AuditService(session)
    log = await audit_svc.get_log(audit_log_id)
    if not log:
        raise HTTPException(status_code=404, detail="审计记录不存在")
    # 校验归属：只有日志所属房源的房东或 admin 可以删除
    if current_user.role.value != "admin":
        from app.services.property_service import PropertyService as _PS
        prop = await _PS(session)._get_property_any(log.resource_id)
        if not prop or prop.landlord_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权删除此记录")
    await audit_svc.delete_log(audit_log_id)


@router.post("/audit/batch-delete")
async def batch_delete_audit_logs(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """批量删除审计日志"""
    from app.services.audit_service import AuditService
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids is required")
    deleted = await AuditService(session).batch_delete_logs(ids)
    return {"deleted": deleted}


@router.post("/audit/clear")
async def clear_audit_logs(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """一键清空当前房东所有房源的审计日志"""
    from app.services.audit_service import AuditService
    deleted = await AuditService(session).clear_logs(current_user.id)
    return {"deleted": deleted}




# ── CRUD ──
@router.get("/{property_id}", response_model=PropertyRead)
async def get_property(property_id: int, session: AsyncSession = Depends(get_db_session)) -> PropertyRead:
    prop = await PropertyService(session).get(property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.patch("/{property_id}", response_model=PropertyRead)
async def update_property(
    property_id: int,
    property_in: PropertyUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> PropertyRead:
    ps = PropertyService(session)
    existing = await ps.get(property_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role.value != "admin" and existing.landlord_id != current_user.id:
        raise HTTPException(status_code=403, detail="Landlords can only update their own properties")
    try:
        prop = await ps.update(property_id, property_in)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    # 异步刷新地图 POI（地址或坐标变更时 Celery 重新搜索）
    generate_map_pois_for_property.delay(prop.id)
    return prop


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> None:
    ps = PropertyService(session)
    existing = await ps.get(property_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role.value != "admin" and existing.landlord_id != current_user.id:
        raise HTTPException(status_code=403, detail="Landlords can only delete their own properties")
    deleted = await ps.delete(property_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Property not found")


@router.get("/{property_id}/history")
async def get_property_history(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    """获取某房源的修改历史（操作审计日志）

    仅返回 resource_type='property' AND resource_id=property_id 的记录。
    房东只能查看自己房源的历史；管理员可查看全部。
    """
    from app.services.audit_service import AuditService
    from app.services.property_service import PropertyService as _PS

    # 校验房源存在 + 归属
    prop = await _PS(session).get(property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if current_user.role.value != "admin" and prop.landlord_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限查看此房源的修改历史")

    logs = await AuditService(session).list_logs(
        skip=skip, limit=limit,
        resource_type="property", resource_id=property_id,
    )
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]

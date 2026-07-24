from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin
from app.models.user import User, UserRole
from app.schemas.user import UserRead
from app.services.audit_service import AuditService
from app.services.embedding_job_service import EmbeddingJobService
from app.services.property_service import PropertyService
from app.services.stats_service import StatsService
from app.services.user_service import UserService

router = APIRouter()


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    return await StatsService(session).get_stats()


@router.get("/logs")
async def list_audit_logs(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
) -> list[dict]:
    logs = await AuditService(session).list_logs(
        skip=skip, limit=limit, action=action, user_id=user_id,
    )
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/logs/resource")
async def list_audit_logs_by_resource(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    resource_type: str = Query(...),
    resource_id: int = Query(...),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    """按资源类型+ID查询审计日志（房源修改历史）"""
    logs = await AuditService(session).list_logs(
        skip=skip, limit=limit,
        resource_type=resource_type, resource_id=resource_id,
    )
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.patch("/properties/{property_id}/status")
async def moderate_property(
    property_id: int,
    new_status: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    valid_statuses = {"available", "rented", "maintenance", "offline", "pending_review"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    from app.schemas.property import PropertyUpdate

    property_obj = await PropertyService(session).update(
        property_id, PropertyUpdate(status=new_status)
    )
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    await AuditService(session).create_log(
        user_id=current_user.id,
        action="property_moderate",
        resource_type="property",
        resource_id=property_id,
        details={"new_status": new_status},
    )
    return {"detail": f"Property {property_id} status set to {new_status}"}


@router.patch("/users/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: int,
    new_role: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> UserRead:
    if new_role not in {"tenant", "landlord", "admin", "bd_manager", "maintenance_worker"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be: tenant, landlord, bd_manager, maintenance_worker, or admin",
        )

    from app.schemas.user import UserUpdate

    user = await UserService(session).update(user_id, UserUpdate(role=UserRole(new_role)))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await AuditService(session).create_log(
        user_id=current_user.id,
        action="user_role_change",
        resource_type="user",
        resource_id=user_id,
        details={"new_role": new_role},
    )
    return user


@router.get("/embeddings/stats")
async def get_embedding_stats(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    return await EmbeddingJobService(session).get_stats()


@router.post("/embeddings/reindex")
async def trigger_reindex(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
    property_id: int | None = Query(default=None),
) -> dict:
    result = await EmbeddingJobService(session).trigger_reindex(property_id)
    await AuditService(session).create_log(
        user_id=current_user.id,
        action="embedding_reindex",
        details={"property_id": property_id},
    )
    return result


@router.get("/properties/pending")
async def list_pending_review_properties(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    """列出所有待人工审核的房源（status=pending_review）"""
    from sqlalchemy import select

    from app.models.property import Property, PropertyStatus
    from app.models.property_image import PropertyImage

    stmt = (
        select(Property)
        .where(Property.status == PropertyStatus.pending_review)
        .order_by(Property.created_at.desc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    properties = list(result)

    return [
        {
            "id": p.id,
            "title": p.title,
            "address": p.address,
            "district": p.district,
            "price_monthly": str(p.price_monthly),
            "area_sqm": str(p.area_sqm) if p.area_sqm else None,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "property_type": p.property_type.value if p.property_type else None,
            "status": p.status.value,
            "description": p.description,
            "created_at": p.created_at.isoformat(),
            "landlord_id": p.landlord_id,
        }
        for p in properties
    ]


@router.get("/landlord-workers-status")
async def get_landlord_workers_status(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Admin查看各房东的维修工状态（Yes/No看板）"""
    from app.models.repair import RepairWorker, WorkerScope, WorkerStatus

    # 获取所有房东
    landlord_stmt = select(User).where(User.role == UserRole.landlord, User.status == "active")
    landlord_result = await session.execute(landlord_stmt)
    landlords = landlord_result.scalars().all()

    result = []
    for ll in landlords:
        # 该房东的apt工人
        workers_stmt = (
            select(RepairWorker)
            .where(
                (RepairWorker.manager_id == ll.id) &
                (RepairWorker.scope == WorkerScope.apartment)
            )
        )
        worker_result = await session.execute(workers_stmt)
        workers = worker_result.scalars().all()

        available_count = sum(1 for w in workers if w.status == WorkerStatus.available)

        result.append({
            "landlord_id": ll.id,
            "landlord_name": ll.username,
            "has_workers": len(workers) > 0,
            "worker_count": len(workers),
            "available_count": available_count,
        })

    return result

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin, require_landlord
from app.models.audit_log import AuditLog
from app.models.booking import Booking, BookingStatus
from app.models.notification import NotificationOutbox, NotificationOutboxStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.user import UserRead
from app.services.audit_service import AuditService
from app.services.property_service import PropertyService
from app.services.stats_service import StatsService
from app.services.user_service import UserService

router = APIRouter()


@router.get("/overview")
async def get_admin_overview(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    role_rows = await session.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role = {
        (role.value if hasattr(role, "value") else str(role)): count
        for role, count in role_rows.all()
    }

    booking_rows = await session.execute(
        select(Booking.status, func.count(Booking.id)).group_by(Booking.status)
    )
    bookings_by_status = {
        (status.value if hasattr(status, "value") else str(status)): count
        for status, count in booking_rows.all()
    }

    payment_rows = await session.execute(
        select(Payment.status, func.count(Payment.id), func.coalesce(func.sum(Payment.settlement_amount_minor), 0))
        .group_by(Payment.status)
    )
    payments_by_status = [
        {
            "status": status.value if hasattr(status, "value") else str(status),
            "count": count,
            "settlement_amount_minor": int(amount or 0),
        }
        for status, count, amount in payment_rows.all()
    ]

    failed_notifications = await session.scalar(
        select(func.count(NotificationOutbox.id)).where(
            NotificationOutbox.status == NotificationOutboxStatus.failed
        )
    )
    recent_logs = await session.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(8)
    )

    return {
        "users": {
            "total": sum(users_by_role.values()),
            "by_role": {
                "admin": users_by_role.get(UserRole.admin.value, 0),
                "tenant": users_by_role.get(UserRole.tenant.value, 0),
                "landlord": users_by_role.get(UserRole.landlord.value, 0),
                "maintenance_worker": users_by_role.get(UserRole.maintenance_worker.value, 0),
            },
        },
        "bookings": {
            "total": sum(bookings_by_status.values()),
            "pending": bookings_by_status.get(BookingStatus.pending.value, 0),
            "paid": bookings_by_status.get(BookingStatus.paid.value, 0),
            "payment_review": bookings_by_status.get(BookingStatus.payment_review.value, 0),
        },
        "payments": {
            "total_count": sum(item["count"] for item in payments_by_status),
            "success_count": next((item["count"] for item in payments_by_status if item["status"] == PaymentStatus.success.value), 0),
            "success_amount_minor": next((item["settlement_amount_minor"] for item in payments_by_status if item["status"] == PaymentStatus.success.value), 0),
            "by_status": payments_by_status,
        },
        "notifications": {
            "failed_outbox": failed_notifications or 0,
        },
        "recent_logs": [
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
            for log in recent_logs
        ],
    }


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_landlord),
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
    if new_role not in {"tenant", "landlord", "admin", "maintenance_worker"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be: tenant, landlord, maintenance_worker, or admin",
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

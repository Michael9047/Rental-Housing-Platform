from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin, require_landlord
from app.models.audit_log import AuditLog
from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract
from app.models.notification import NotificationOutbox, NotificationOutboxStatus
from app.models.payment import Payment, PaymentStatus
from app.models.pms_connection import PMSConnection, PMSSyncStatus
from app.models.system_alert import (
    SystemAlert as PersistedSystemAlert,
    SystemAlertSeverity,
    SystemAlertStatus,
)
from app.models.user import User, UserRole
from app.schemas.system_alert import SystemAlertCreate
from app.schemas.user import UserRead
from app.services.audit_service import AuditService
from app.services.payment_provider import provider_availability
from app.services.pms.sync_service import PMSSyncService
from app.services.property_service import PropertyService
from app.services.stats_service import StatsService
from app.services.user_service import UserService

router = APIRouter()


class SystemAlertResolveRequest(BaseModel):
    note: str | None = None


def _alert_action(
    action_type: str | None,
    action_label: str | None,
    action_resource_id: str | int | None,
) -> dict | None:
    if not action_type or not action_label:
        return None
    return {
        "type": action_type,
        "label": action_label,
        "resource_id": action_resource_id,
    }


HUMAN_PROCESS_ALERT_CATEGORIES = {"预约", "维修"}
HUMAN_PROCESS_ALERT_SOURCE_PREFIXES = ("booking", "repair", "maintenance")
HUMAN_PROCESS_ALERT_KEYWORDS = (
    "预约超时",
    "待处理预约",
    "booking_pending",
    "booking_payment",
    "payment_review",
    "payment_expired",
    "维修未处理",
    "维修待派单",
    "repair_pending",
    "repair_assigned",
    "repair_stalled",
    "repair_completed",
    "合同未签署",
    "未签署合同",
    "contract_unsigned",
    "待人工",
    "人工审核",
    "退款核对",
)


def _is_system_runtime_alert(row: PersistedSystemAlert) -> bool:
    """过滤人为流程待办，只保留系统运行异常。"""
    if row.category in HUMAN_PROCESS_ALERT_CATEGORIES:
        return False

    source = (row.source or "").lower()
    if source.startswith(HUMAN_PROCESS_ALERT_SOURCE_PREFIXES):
        return False

    searchable = " ".join(
        str(value or "")
        for value in (
            row.source,
            row.source_id,
            row.action_type,
            row.action_label,
            row.title,
            row.summary,
            row.detail,
        )
    ).lower()
    return not any(keyword.lower() in searchable for keyword in HUMAN_PROCESS_ALERT_KEYWORDS)


def _persisted_alert_to_card(row: PersistedSystemAlert) -> dict:
    return {
        "id": f"system:{row.id}",
        "category": row.category,
        "severity": row.severity.value if hasattr(row.severity, "value") else str(row.severity),
        "title": row.title,
        "summary": row.summary,
        "detail": row.detail or "",
        "source": row.source,
        "source_id": row.source_id or row.id,
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "updated_at": row.updated_at.isoformat(),
        "action": _alert_action(
            row.action_type or "resolve_system_alert",
            row.action_label or "标记处理",
            row.action_resource_id or row.id,
        ),
    }


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


@router.get("/system-alerts")
async def list_system_alerts(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    include_resolved: bool = Query(default=False),
) -> list[dict]:
    now = datetime.now(timezone.utc)
    alerts: list[dict] = []

    # 只汇总系统运行异常：服务投递、外部对接、支付通道、后台任务产物等。
    # 预约超时、维修未处理、合同未签署等人为流程待办不进入管理员异常检测。
    persisted_stmt = select(PersistedSystemAlert).order_by(PersistedSystemAlert.updated_at.desc()).limit(60)
    if not include_resolved:
        persisted_stmt = persisted_stmt.where(PersistedSystemAlert.status != SystemAlertStatus.resolved)
    persisted_rows = await session.scalars(persisted_stmt)
    alerts.extend(_persisted_alert_to_card(row) for row in persisted_rows if _is_system_runtime_alert(row))

    failed_outbox_rows = await session.scalars(
        select(NotificationOutbox)
        .where(NotificationOutbox.status == NotificationOutboxStatus.failed)
        .order_by(NotificationOutbox.updated_at.desc())
        .limit(20)
    )
    for row in failed_outbox_rows:
        alerts.append({
            "id": f"notification:{row.id}",
            "category": "通知",
            "severity": "high" if row.attempts >= 3 else "medium",
            "title": "通知发送失败",
            "summary": f"{row.event_type} 发送失败，已尝试 {row.attempts} 次",
            "detail": row.last_error or "通知投递失败，等待管理员检查或重试。",
            "source": "notification_outbox",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": {
                "type": "retry_notification",
                "label": "重新发送",
                "resource_id": row.id,
            },
        })

    contract_pdf_failed_rows = await session.scalars(
        select(Contract)
        .where(Contract.pdf_status == "failed")
        .order_by(Contract.updated_at.desc())
        .limit(12)
    )
    for row in contract_pdf_failed_rows:
        alerts.append({
            "id": f"contract_pdf:{row.id}",
            "category": "合同",
            "severity": "high",
            "title": "合同 PDF 生成失败",
            "summary": f"合同 {row.agreement_number or row.id} 无法生成签署文件",
            "detail": row.pdf_last_error or "PDF 生成服务未返回明确错误。",
            "source": "contract",
            "source_id": row.id,
            "status": row.pdf_status,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    pms_rows = await session.scalars(
        select(PMSConnection).order_by(PMSConnection.updated_at.desc()).limit(50)
    )
    for conn in pms_rows:
        updated_at = conn.updated_at.isoformat()
        base = {
            "category": "对接",
            "source": "pms_connection",
            "source_id": conn.id,
            "updated_at": updated_at,
        }
        if conn.sync_status == PMSSyncStatus.failed:
            alerts.append({
                **base,
                "id": f"pms_failed:{conn.id}",
                "severity": "high",
                "title": "PMS 对接同步失败",
                "summary": f"{conn.label} 上次同步失败",
                "detail": conn.last_sync_error or "外部 PMS 接口同步失败。",
                "status": conn.sync_status.value,
                "action": {
                    "type": "retry_pms_sync",
                    "label": "重新同步",
                    "resource_id": conn.id,
                },
            })
        if conn.is_active and not conn.base_url.startswith("mock://") and not conn.api_key:
            alerts.append({
                **base,
                "id": f"pms_api_key:{conn.id}",
                "severity": "high",
                "title": "PMS API Key 缺失或已失效",
                "summary": f"{conn.label} 未配置有效 API Key",
                "detail": "外部 PMS API 凭证缺失，可能是未配置、过期或被平台撤销。",
                "status": "credential_missing",
                "action": None,
            })
        if conn.is_active and conn.last_synced_at is not None:
            synced_at = conn.last_synced_at
            if synced_at.tzinfo is None:
                synced_at = synced_at.replace(tzinfo=timezone.utc)
            if now - synced_at > timedelta(hours=24):
                alerts.append({
                    **base,
                    "id": f"pms_stale:{conn.id}",
                    "severity": "medium",
                    "title": "PMS 同步任务停滞",
                    "summary": f"{conn.label} 超过 24 小时未同步",
                    "detail": f"上次同步时间：{conn.last_synced_at.isoformat()}，请检查定时任务或外部 API 状态。",
                    "status": "stale",
                    "action": {
                        "type": "retry_pms_sync",
                        "label": "重新同步",
                        "resource_id": conn.id,
                    },
                })

    for item in provider_availability():
        if not item.available and not item.test_mode:
            alerts.append({
                "id": f"payment_provider:{item.method.value}",
                "category": "支付",
                "severity": "medium",
                "title": "支付接口未开通",
                "summary": f"{item.method.value} 当前不可用",
                "detail": item.reason or "支付服务商配置缺失或尚未完成联调。",
                "source": "payment_provider",
                "source_id": item.method.value,
                "status": "unavailable",
                "updated_at": now.isoformat(),
                "action": None,
            })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["updated_at"]), reverse=False)
    return alerts[:60]


@router.post("/system-alerts", status_code=status.HTTP_201_CREATED)
async def create_system_alert(
    body: SystemAlertCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    alert = PersistedSystemAlert(
        category=body.category,
        severity=SystemAlertSeverity(body.severity),
        title=body.title,
        summary=body.summary,
        detail=body.detail,
        source=body.source,
        source_id=body.source_id,
        status=SystemAlertStatus.open,
        action_type=body.action_type or "resolve_system_alert",
        action_label=body.action_label or "标记处理",
        action_resource_id=body.action_resource_id,
        extra=body.extra,
        reported_by_id=current_user.id,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return _persisted_alert_to_card(alert)


@router.patch("/system-alerts/{alert_id}/resolve")
async def resolve_system_alert(
    alert_id: int,
    body: SystemAlertResolveRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    alert = await session.get(PersistedSystemAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="System alert not found")
    details = alert.extra or {}
    if body and body.note:
        details["resolve_note"] = body.note
    alert.extra = details or None
    alert.mark_resolved(current_user.id)
    await session.commit()
    return {"id": alert.id, "status": alert.status.value}


@router.post("/pms-connections/{connection_id}/sync")
async def retry_pms_connection_sync(
    connection_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    """异常处理页触发 PMS 连接重新同步。"""
    try:
        stats = await PMSSyncService(session).sync_connection(connection_id)
        return {"status": "success", **stats}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PMS sync failed: {exc}",
        ) from exc


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

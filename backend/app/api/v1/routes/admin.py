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
from app.models.repair import RepairRequest, RepairStatus
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

    persisted_stmt = select(PersistedSystemAlert).order_by(PersistedSystemAlert.updated_at.desc()).limit(60)
    if not include_resolved:
        persisted_stmt = persisted_stmt.where(PersistedSystemAlert.status != SystemAlertStatus.resolved)
    persisted_rows = await session.scalars(persisted_stmt)
    alerts.extend(_persisted_alert_to_card(row) for row in persisted_rows)

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

    overdue_booking_rows = await session.scalars(
        select(Booking)
        .where(
            Booking.status == BookingStatus.pending,
            Booking.created_at < now - timedelta(hours=2),
        )
        .order_by(Booking.created_at.asc())
        .limit(12)
    )
    for row in overdue_booking_rows:
        alerts.append({
            "id": f"booking_pending:{row.id}",
            "category": "预约",
            "severity": "high",
            "title": "预约待处理超时",
            "summary": f"预约 #{row.id} 超过 2 小时仍未处理",
            "detail": f"租客用户 ID：{row.user_id}，户型 ID：{row.unit_type_id or '-'}，预计入住：{row.scheduled_date or '-'}。",
            "source": "booking",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    payment_review_booking_rows = await session.scalars(
        select(Booking)
        .where(
            Booking.status == BookingStatus.payment_review,
            Booking.updated_at < now - timedelta(hours=2),
        )
        .order_by(Booking.updated_at.asc())
        .limit(12)
    )
    for row in payment_review_booking_rows:
        alerts.append({
            "id": f"booking_payment_review:{row.id}",
            "category": "支付",
            "severity": "high",
            "title": "订单支付待人工核验",
            "summary": f"订单 #{row.id} 已进入支付核验超过 2 小时",
            "detail": "需要核对支付流水、订单金额与合同状态，避免租客订单卡在待确认状态。",
            "source": "booking",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    expired_payment_booking_rows = await session.scalars(
        select(Booking)
        .where(
            Booking.status.in_([BookingStatus.payment_pending, BookingStatus.payment_processing]),
            Booking.payment_expires_at.is_not(None),
            Booking.payment_expires_at < now,
        )
        .order_by(Booking.payment_expires_at.asc())
        .limit(12)
    )
    for row in expired_payment_booking_rows:
        alerts.append({
            "id": f"booking_payment_expired:{row.id}",
            "category": "支付",
            "severity": "medium",
            "title": "支付窗口已过期但订单未关闭",
            "summary": f"订单 #{row.id} 支付有效期已过",
            "detail": f"过期时间：{row.payment_expires_at.isoformat() if row.payment_expires_at else '-'}，当前状态：{row.status.value}。",
            "source": "booking",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    failed_payment_rows = await session.scalars(
        select(Payment)
        .where(Payment.status.in_([PaymentStatus.failed, PaymentStatus.review, PaymentStatus.refund_pending]))
        .order_by(Payment.updated_at.desc())
        .limit(12)
    )
    for row in failed_payment_rows:
        severity = "high" if row.status in (PaymentStatus.review, PaymentStatus.refund_pending) else "medium"
        title = {
            PaymentStatus.failed: "支付失败记录待查看",
            PaymentStatus.review: "支付流水待复核",
            PaymentStatus.refund_pending: "退款待处理",
        }.get(row.status, "支付异常")
        alerts.append({
            "id": f"payment:{row.id}",
            "category": "支付",
            "severity": severity,
            "title": title,
            "summary": f"支付单 {row.order_id} 当前状态：{row.status.value}",
            "detail": row.trade_state_desc or f"金额：{row.amount}，预约 ID：{row.booking_id}，支付方式：{row.payment_method}。",
            "source": "payment",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    pending_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status.in_([RepairStatus.pending, RepairStatus.pending_escalated]),
            RepairRequest.updated_at < now - timedelta(hours=4),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in pending_repair_rows:
        alerts.append({
            "id": f"repair_pending:{row.id}",
            "category": "维修",
            "severity": "high",
            "title": "维修工单待派单超时",
            "summary": f"工单 #{row.id} 超过 4 小时未派单",
            "detail": f"问题类型：{row.issue_type.value}，租客 ID：{row.tenant_id}，负责人 ID：{row.bm_id}。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    assigned_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status == RepairStatus.assigned,
            RepairRequest.updated_at < now - timedelta(hours=24),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in assigned_repair_rows:
        alerts.append({
            "id": f"repair_assigned:{row.id}",
            "category": "维修",
            "severity": "medium",
            "title": "维修已派单但未开工",
            "summary": f"工单 #{row.id} 已派单超过 24 小时",
            "detail": f"维修工用户 ID：{row.assigned_worker_id or '-'}，计划时间：{row.scheduled_time or '-'}。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    stalled_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status == RepairStatus.in_progress,
            RepairRequest.updated_at < now - timedelta(hours=48),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in stalled_repair_rows:
        alerts.append({
            "id": f"repair_stalled:{row.id}",
            "category": "维修",
            "severity": "high",
            "title": "维修进度停滞",
            "summary": f"工单 #{row.id} 维修中超过 48 小时未更新",
            "detail": f"维修工用户 ID：{row.assigned_worker_id or '-'}，最近记录：{row.work_record or '暂无维修记录'}。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
        })

    completed_unconfirmed_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status == RepairStatus.completed,
            RepairRequest.updated_at < now - timedelta(hours=48),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in completed_unconfirmed_repair_rows:
        alerts.append({
            "id": f"repair_unconfirmed:{row.id}",
            "category": "维修",
            "severity": "low",
            "title": "维修完成待租客确认",
            "summary": f"工单 #{row.id} 完成超过 48 小时未确认",
            "detail": "需要提醒租客确认维修结果，或由管理员核实后结案。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "action": None,
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

    unsigned_contract_rows = await session.scalars(
        select(Contract)
        .where(
            Contract.status == "generated",
            Contract.updated_at < now - timedelta(hours=24),
        )
        .order_by(Contract.updated_at.asc())
        .limit(12)
    )
    for row in unsigned_contract_rows:
        alerts.append({
            "id": f"contract_unsigned:{row.id}",
            "category": "合同",
            "severity": "medium",
            "title": "合同生成后未签署",
            "summary": f"合同 {row.agreement_number or row.id} 超过 24 小时未签署",
            "detail": f"预约 ID：{row.booking_id}，租客用户 ID：{row.tenant_id}，模板：{row.template_name}。",
            "source": "contract",
            "source_id": row.id,
            "status": row.status,
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
        if conn.sync_status == PMSSyncStatus.pending_review:
            alerts.append({
                **base,
                "id": f"pms_review:{conn.id}",
                "severity": "medium",
                "title": "PMS 映射待确认",
                "summary": f"{conn.label} 有字段映射需要人工确认",
                "detail": "对接字段或房型映射需要确认后再同步入库。",
                "status": conn.sync_status.value,
                "action": None,
            })
        if not conn.is_active:
            alerts.append({
                **base,
                "id": f"pms_inactive:{conn.id}",
                "severity": "low",
                "title": "PMS 对接已停用",
                "summary": f"{conn.label} 当前未启用",
                "detail": "该公寓不会继续从 PMS 自动同步房源。",
                "status": "inactive",
                "action": None,
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
        if conn.is_active:
            if conn.last_synced_at is None:
                alerts.append({
                    **base,
                    "id": f"pms_never_synced:{conn.id}",
                    "severity": "medium",
                    "title": "PMS 从未完成同步",
                    "summary": f"{conn.label} 尚无成功同步记录",
                    "detail": "该对接创建后还没有完成过一次同步。",
                    "status": "never_synced",
                    "action": {
                        "type": "retry_pms_sync",
                        "label": "立即同步",
                        "resource_id": conn.id,
                    },
                })
            else:
                synced_at = conn.last_synced_at
                if synced_at.tzinfo is None:
                    synced_at = synced_at.replace(tzinfo=timezone.utc)
                if now - synced_at > timedelta(hours=24):
                    alerts.append({
                        **base,
                        "id": f"pms_stale:{conn.id}",
                        "severity": "medium",
                        "title": "PMS 同步超时",
                        "summary": f"{conn.label} 超过 24 小时未同步",
                        "detail": f"上次同步时间：{conn.last_synced_at.isoformat()}",
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

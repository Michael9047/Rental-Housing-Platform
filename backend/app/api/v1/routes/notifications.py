from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin
from sqlalchemy import select
from datetime import datetime, timezone
from app.models.notification import NotificationOutbox, NotificationOutboxStatus, NotificationType
from app.models.payment import Payment
from app.models.booking import Booking, BookingStatus
from app.models.user import User, UserRole
from app.schemas.notification import NotificationRead, NotificationListResponse, UnreadCount
from app.services.notification_service import NotificationService
from app.services.tenant_order_service import TenantOrderService

router = APIRouter()


def _mask_email(value: str | None) -> str:
    """管理员预览模拟邮件时仍不暴露完整邮箱地址。"""
    if not value:
        return "未提供"
    if "@" not in value:
        return "***"
    name, domain = value.split("@", 1)
    return f"{name[:1]}***@{domain}"


@router.get("/admin/outbox")
async def list_failed_outbox(session: AsyncSession = Depends(get_db_session), _: User = Depends(require_admin)) -> list[dict]:
    rows = list(await session.scalars(select(NotificationOutbox).where(NotificationOutbox.status == NotificationOutboxStatus.failed).order_by(NotificationOutbox.updated_at.desc()).limit(200)))
    return [{"id":r.id,"event_key":r.event_key,"event_type":r.event_type,"user_id":r.user_id,"booking_id":r.booking_id,"template_version":r.template_version,"status":r.status.value,"attempts":r.attempts,"last_error":r.last_error,"updated_at":r.updated_at} for r in rows]


@router.get("/admin/mailbox")
async def list_simulated_mailbox(
    limit: int = Query(default=100, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    """从既有邮件 outbox 读取模拟邮件预览，不重新投递或调用 SMTP。"""
    rows = list(await session.scalars(
        select(NotificationOutbox)
        .where(NotificationOutbox.channel == "email")
        .order_by(NotificationOutbox.queued_at.desc())
        .limit(limit)
    ))
    items = []
    for row in rows:
        payload = row.payload or {}
        items.append({
            "id": row.id,
            "event_type": row.event_type,
            "booking_id": row.booking_id,
            "recipient": _mask_email(row.recipient_email or payload.get("recipient")),
            "title": str(payload.get("title") or payload.get("event_title") or row.event_type),
            "body": str(payload.get("body") or "该历史邮件未保存正文。"),
            "status": row.status.value,
            "attempts": row.attempts,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
            "queued_at": row.queued_at.isoformat(),
            "last_error": row.last_error,
            "simulated": bool(payload.get("simulated")),
        })
    return {"items": items}


@router.post("/admin/outbox/{outbox_id}/retry")
async def retry_outbox(outbox_id: str, session: AsyncSession = Depends(get_db_session), _: User = Depends(require_admin)) -> dict:
    row = await session.get(NotificationOutbox, outbox_id)
    if not row: raise HTTPException(404, "通知事件不存在")
    if row.status == NotificationOutboxStatus.sent: raise HTTPException(409, "通知已经发送")
    row.status=NotificationOutboxStatus.pending; row.next_attempt_at=datetime.now(timezone.utc); row.last_error=None
    await session.commit(); return {"id":row.id,"status":"pending"}


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = 1,
    page_size: int = 50,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    # 兼容通知功能接入前已支付的订单：仅为当前可管理范围补齐一次管理员待合同确认提醒。
    if current_user.role in {UserRole.admin, UserRole.landlord}:
        paid_rows = list(await session.scalars(select(Booking).where(Booking.status == BookingStatus.paid)))
        notifier = NotificationService(session)
        for booking in paid_rows:
            if current_user.role == UserRole.admin or booking.bm_id == current_user.id:
                await notifier.add_admin_order_notifications(booking.id, booking.bm_id, booking.unit_type_id, NotificationType.payment_received, "新支付订单待确认合同", f"订单 #{booking.id} 已完成支付。请在 3 个自然日内确认房号、合同信息并上传合同。")
        await session.commit()
    rows, total = await NotificationService(session).list_by_user(current_user.id, max(1, page), min(max(1, page_size), 100))
    items: list[NotificationRead] = []
    order_service = TenantOrderService(session)
    for row in rows:
        item = NotificationRead.model_validate(row)
        # 仅使用结构化关联字段；绝不从通知正文解析订单号。
        # 历史支付通知曾将支付平台订单号写入 entity_id，这里仅在服务端
        # 通过 Payment.order_id 反查受信任的 booking_id，兼容旧消息跳转。
        booking_id: int | None = None
        if row.entity_type == "order":
            if row.entity_id and row.entity_id.isdigit():
                booking_id = int(row.entity_id)
            elif row.order_id and row.order_id.isdigit():
                booking_id = int(row.order_id)
            elif row.entity_id:
                booking_id = await session.scalar(
                    select(Payment.booking_id).where(Payment.order_id == row.entity_id)
                )
        if booking_id is not None:
            try:
                eligibility = await order_service.payment_eligibility(booking_id, current_user.id)
                item = item.model_copy(update={
                    "entity_id": str(booking_id),
                    "can_pay": eligibility.can_pay,
                    "payment_status": eligibility.payment_status,
                    "order_status": eligibility.order_status,
                })
            except LookupError:
                # 历史通知仍可展示，关联订单失效时不影响整个列表。
                item = item.model_copy(update={"entity_id": str(booking_id)})
        items.append(item)
    return NotificationListResponse(items=items, total=total, page=max(1, page), page_size=min(max(1, page_size), 100))


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    notification = await NotificationService(session).mark_read(notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.patch("/read-all")
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    await NotificationService(session).mark_all_read(current_user.id)
    return {"detail": "All notifications marked as read"}


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UnreadCount:
    count = await NotificationService(session).get_unread_count(current_user.id)
    return UnreadCount(count=count)

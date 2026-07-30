from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin
from sqlalchemy import select
from datetime import datetime, timezone
from app.models.notification import NotificationOutbox, NotificationOutboxStatus
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationListResponse, UnreadCount
from app.services.notification_service import NotificationService
from app.services.tenant_order_service import TenantOrderService

router = APIRouter()


@router.get("/admin/outbox")
async def list_failed_outbox(session: AsyncSession = Depends(get_db_session), _: User = Depends(require_admin)) -> list[dict]:
    rows = list(await session.scalars(select(NotificationOutbox).where(NotificationOutbox.status == NotificationOutboxStatus.failed).order_by(NotificationOutbox.updated_at.desc()).limit(200)))
    return [{"id":r.id,"event_key":r.event_key,"event_type":r.event_type,"user_id":r.user_id,"booking_id":r.booking_id,"template_version":r.template_version,"status":r.status.value,"attempts":r.attempts,"last_error":r.last_error,"updated_at":r.updated_at} for r in rows]


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
    rows, total = await NotificationService(session).list_by_user(current_user.id, max(1, page), min(max(1, page_size), 100))
    items: list[NotificationRead] = []
    order_service = TenantOrderService(session)
    for row in rows:
        item = NotificationRead.model_validate(row)
        # 仅使用结构化 entity_id；绝不从通知正文解析订单号。
        if row.entity_type == "order" and row.entity_id and row.entity_id.isdigit():
            try:
                eligibility = await order_service.payment_eligibility(int(row.entity_id), current_user.id)
                item = item.model_copy(update={
                    "can_pay": eligibility.can_pay,
                    "payment_status": eligibility.payment_status,
                    "order_status": eligibility.order_status,
                })
            except LookupError:
                # 历史通知仍可展示，关联订单失效时不影响整个列表。
                pass
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

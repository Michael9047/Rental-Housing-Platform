from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.notification import NotificationRead, UnreadCount
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[NotificationRead]:
    return await NotificationService(session).list_by_user(current_user.id)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    notification = await NotificationService(session).mark_read(notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
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

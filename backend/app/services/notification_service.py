from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_notification(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        content: str,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def list_by_user(self, user_id: int) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def mark_read(self, notification_id: int) -> Notification | None:
        notification = await self.session.get(Notification, notification_id)
        if not notification:
            return None
        notification.is_read = True
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def mark_all_read(self, user_id: int) -> None:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_unread_count(self, user_id: int) -> int:
        stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

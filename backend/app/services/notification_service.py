import logging
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)

# Per-notification-type channel templates
_CHANNEL_META: dict[NotificationType, dict] = {
    NotificationType.booking_created: {
        "wechat_template": "booking_confirm_template_id",
    },
    NotificationType.booking_approved: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.booking_rejected: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.booking_cancelled: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.booking_completed: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.payment_received: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.system: {
        "wechat_template": "status_update_template_id",
    },
}


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── DB operations (unchanged signatures) ────────────────────────

    async def create_notification(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        content: str,
        channels: Optional[list[str]] = None,
    ) -> Notification:
        """Create a DB notification record and dispatch to push channels.

        channels: list of "wechat", "sms", "email". Defaults to all three.
        Channel dispatch failures are logged but do not block DB write.
        """
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)

        # Dispatch to push channels (fire-and-forget via Celery)
        await self._dispatch_channels(user_id, type, title, content, channels)

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

    # ── Channel dispatch ────────────────────────────────────────────

    async def _dispatch_channels(
        self,
        user_id: int,
        ntype: NotificationType,
        title: str,
        content: str,
        channels: Optional[list[str]] = None,
    ) -> None:
        """Fire Celery tasks for each requested push channel."""
        if channels is None:
            channels = ["wechat", "sms", "email"]

        meta = _CHANNEL_META.get(ntype, {})

        try:
            from app.tasks.notification_tasks import (
                send_sms_notification,
                send_email_notification,
                send_wechat_template_message,
            )

            if "wechat" in channels:
                try:
                    template_id = meta.get("wechat_template", "status_update_template_id")
                    wechat_data = {
                        "first": {"value": title},
                        "keyword1": {"value": content or ""},
                        "keyword2": {"value": ""},
                        "remark": {"value": "点击查看详情。"},
                    }
                    send_wechat_template_message.delay(
                        user_id=user_id,
                        template_id=template_id,
                        data=wechat_data,
                        page="pages/booking/detail",
                    )
                except Exception as exc:
                    logger.warning("Failed to dispatch WeChat notification: %s", exc)

            if "sms" in channels:
                try:
                    send_sms_notification.delay(user_id=user_id, content=content or title)
                except Exception as exc:
                    logger.warning("Failed to dispatch SMS notification: %s", exc)

            if "email" in channels:
                try:
                    send_email_notification.delay(
                        user_id=user_id,
                        subject=title,
                        html_body=f"<h3>{title}</h3><p>{content or ''}</p><p>点击查看详情。</p>",
                    )
                except Exception as exc:
                    logger.warning("Failed to dispatch Email notification: %s", exc)
        except Exception as exc:
            logger.warning("Failed to import notification tasks: %s", exc)

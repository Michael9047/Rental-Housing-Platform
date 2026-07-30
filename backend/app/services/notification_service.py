import logging
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)

# 各通知类型的渠道元数据
# - wechat_template: 微信模板消息 ID（暂未启用）
# - sms_template: 通知短信模板 CODE，需在阿里云控制台申请后填入
#   没有配置 sms_template 的类型发短信时会走通用模板（title + content）
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
    NotificationType.payment_created: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.payment_failed: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.payment_expired: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.contract_generated: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.contract_signed: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.auth_registration: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.auth_password_reset: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.repair_created: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.repair_assigned: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.repair_completed: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.repair_status_change: {
        "wechat_template": "status_update_template_id",
    },
    NotificationType.system: {
        "wechat_template": "status_update_template_id",
    },
}

# 通知类型 → 邮件模板映射（仅需自定义模板的类型）
_NOTIFICATION_EMAIL_TEMPLATE: dict[NotificationType, str] = {
    NotificationType.payment_created: "payment_created",
    NotificationType.payment_received: "payment_received",
    NotificationType.payment_failed: "payment_failed",
    NotificationType.payment_expired: "payment_expired",
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
        email_attachments: Optional[list[dict]] = None,
    ) -> Notification:
        """Create a DB notification record and dispatch to push channels.

        channels: list of "wechat", "sms", "email". Defaults to all three.
        email_attachments: list of {"filename": str, "content_b64": str} for email.
        Channel dispatch failures are logged but do not block DB write.
        """
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            body=content,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)

        # Dispatch to push channels (fire-and-forget via Celery)
        await self._dispatch_channels(
            user_id, type, title, content, channels, email_attachments,
        )

        return notification

    async def list_by_user(self, user_id: int, page: int = 1, page_size: int = 50) -> tuple[list[Notification], int]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        total = await self.session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id)) or 0
        result = await self.session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))
        return list(result), int(total)

    async def mark_read(self, notification_id: int, user_id: int) -> Notification | None:
        notification = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
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
        email_attachments: Optional[list[dict]] = None,
    ) -> None:
        """Fire Celery tasks for each requested push channel."""
        if channels is None:
            channels = ["email"]  # SMS 仅用于验证码场景，通知走邮件

        meta = _CHANNEL_META.get(ntype, {})

        try:
            from app.tasks.notification_tasks import (
                send_sms_notification,
                send_email_notification,
            )

            # 微信暂不启用
            # if "wechat" in channels:
            #     ...

            if "sms" in channels:
                try:
                    send_sms_notification.delay(
                        user_id=user_id,
                        notification_type=ntype.value,
                        title=title,
                        content=content or title,
                    )
                except Exception as exc:
                    logger.warning("Failed to dispatch SMS notify: %s", exc)

            if "email" in channels:
                try:
                    # 优先使用模板：根据通知类型匹配对应邮件模板
                    template_name = _NOTIFICATION_EMAIL_TEMPLATE.get(ntype)
                    if template_name:
                        from app.tasks.notification_tasks import send_email_notification_with_template
                        send_email_notification_with_template.delay(
                            user_id=user_id,
                            subject=title,
                            template_name=template_name,
                            context={"content": content or ""},
                        )
                    else:
                        send_email_notification.delay(
                            user_id=user_id,
                            subject=title,
                            html_body=f"<h3>{title}</h3><p>{content or ''}</p><p>点击查看详情。</p>",
                            attachments=email_attachments,
                        )
                except Exception as exc:
                    logger.warning("Failed to dispatch Email notification: %s", exc)
        except Exception as exc:
            logger.warning("Failed to import notification tasks: %s", exc)

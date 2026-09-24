import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import cast, func, literal, select, type_coerce, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.models.booking import Booking
from app.models.contract import Contract
from app.models.payment import Payment, PaymentStatus
from app.models.unit_type import UnitType
from app.models.user import User, UserRole
from app.core.config import get_settings
from app.services.notification_link_service import notification_action_label, notification_target

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
        entity_type: str | None = None,
        entity_id: str | None = None,
        order_id: str | None = None,
        agreement_id: str | None = None,
        unit_type_id: int | None = None,
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
            entity_type=entity_type,
            entity_id=entity_id,
            order_id=order_id,
            agreement_id=agreement_id,
            unit_type_id=unit_type_id,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)

        # 站内信提交后再投递外部渠道，失败不回滚已提交的业务状态。
        await self._dispatch_channels(
            user_id, type, title, content, channels, email_attachments,
            entity_type=entity_type, entity_id=entity_id,
        )

        return notification

    async def add_admin_order_notifications(
        self,
        booking_id: int,
        bm_id: int | None,
        unit_type_id: int | None,
        notification_type: NotificationType,
        title: str,
        content: str,
        agreement_id: str | None = None,
    ) -> None:
        """向负责 BM 与超级管理员追加订单站内消息；由调用方统一提交事务。"""
        booking = await self.session.get(Booking, booking_id)
        payment = await self.session.scalar(
            select(Payment)
            .where(Payment.booking_id == booking_id, Payment.status == PaymentStatus.success)
            .order_by(Payment.paid_at.desc())
        )
        unit_type = await self.session.get(UnitType, unit_type_id) if unit_type_id else None
        confirmation_deadline = (
            (payment.paid_at + timedelta(days=3)).isoformat()
            if payment and payment.paid_at else "待确认"
        )
        recipients: dict[int, User] = {}
        if bm_id:
            bm = await self.session.get(User, bm_id)
            if bm:
                recipients[bm.id] = bm
        admins = await self.session.scalars(select(User).where(User.role == UserRole.admin))
        recipients.update({admin.id: admin for admin in admins})
        for recipient in recipients.values():
            manager_target = notification_target(notification_type.value, recipient.role, booking_id)
            manager_url = f"{get_settings().frontend_url.rstrip('/')}{manager_target}"
            existing = await self.session.scalar(select(Notification.id).where(
                Notification.user_id == recipient.id,
                Notification.type == literal(notification_type.value),
                Notification.entity_type == "order",
                Notification.entity_id == str(booking_id),
                Notification.title == title,
            ))
            if existing:
                continue
            self.session.add(Notification(
                user_id=recipient.id, type=notification_type, title=title,
                content=content, body=content, entity_type="order", entity_id=str(booking_id),
                order_id=str(booking_id), agreement_id=agreement_id, unit_type_id=unit_type_id,
            ))
            # 开发环境 Mailpit 直接接收模拟邮件；失败只记录日志，绝不影响站内消息或订单。
            if recipient.email:
                try:
                    from app.services.email_service import EmailService
                    await EmailService().send_with_template(
                        recipient.email, title,
                        "order_event",
                        {
                            "event_title": title,
                            "user_name": recipient.username,
                            "order_number": str(booking_id),
                            "property_name": unit_type.name if unit_type else "订单关联房源",
                            "move_in_date": booking.scheduled_date if booking else "待确认",
                            "tenancy_months": booking.lease_months if booking else 0,
                            "amount": (
                                f"{payment.settlement_amount_minor / 100:.2f} {payment.settlement_currency}"
                                if payment else "待确认"
                            ),
                            "status": booking.status.value if booking else "待确认",
                            "payment_deadline": confirmation_deadline,
                            "order_url": manager_url,
                            "action_label": notification_action_label(notification_type.value, recipient.role),
                            "support_email": get_settings().support_email,
                        },
                    )
                except Exception:
                    logger.exception("管理员模拟邮件投递失败 booking_id=%s user_id=%s", booking_id, recipient.id)

    async def list_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 50,
        *,
        unread_only: bool = False,
        business_only: bool = False,
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read == False)
        if business_only:
            from sqlalchemy import or_
            conditions.append(
                or_(
                    Notification.entity_type == "order",
                    Notification.entity_type == "contract",
                    Notification.entity_type == "payment",
                )
            )
        base_where = conditions[0]
        for c in conditions[1:]:
            base_where = base_where & c

        stmt = (
            select(Notification)
            .where(base_where)
            .order_by(Notification.created_at.desc())
        )
        total = await self.session.scalar(
            select(func.count()).select_from(Notification).where(base_where)
        ) or 0
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
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        """发送后置渠道；订单邮件在开发环境直接投递 Mailpit。"""
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
                    await self._send_order_email_direct(
                        user_id=user_id,
                        notification_type=ntype,
                        title=title,
                        entity_type=entity_type,
                        entity_id=entity_id,
                    )
                except Exception as exc:
                    logger.warning("Failed to dispatch Email notification: %s", exc)
        except Exception as exc:
            logger.warning("Failed to import notification tasks: %s", exc)

    async def _send_order_email_direct(
        self,
        *,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        entity_type: str | None,
        entity_id: str | None,
    ) -> None:
        """直接调用既有 EmailService，避免开发环境因 Celery worker 未运行而漏发。"""
        recipient = await self.session.get(User, user_id)
        if not recipient or not recipient.email:
            logger.warning("订单邮件跳过：用户没有邮箱 user_id=%s", user_id)
            return

        booking_id = int(entity_id) if entity_type == "order" and entity_id and entity_id.isdigit() else None
        booking = await self.session.get(Booking, booking_id) if booking_id else None
        payment = None
        contract = None
        unit_type = None
        if booking:
            payment = await self.session.scalar(
                select(Payment)
                .where(Payment.booking_id == booking.id)
                .order_by(Payment.paid_at.desc().nullslast(), Payment.created_at.desc())
            )
            contract = await self.session.scalar(
                select(Contract).where(Contract.booking_id == booking.id).order_by(Contract.version.desc())
            )
            unit_type = await self.session.get(UnitType, booking.unit_type_id) if booking.unit_type_id else None

        event_type = "CONTRACT_SENT" if notification_type == NotificationType.contract_generated else notification_type.value
        target = notification_target(event_type, recipient.role, booking_id or 0)
        order_url = f"{get_settings().frontend_url.rstrip('/')}{target}"
        deadline = (
            (contract.generated_at + timedelta(days=7)).isoformat()
            if notification_type == NotificationType.contract_generated and contract and contract.generated_at
            else booking.payment_expires_at.isoformat() if booking and booking.payment_expires_at else "请以订单详情显示的时间为准"
        )
        amount = f"{payment.settlement_amount_minor / 100:.2f} {payment.settlement_currency}" if payment else "待确认"
        context = {
            "event_title": title,
            "user_name": recipient.username,
            "order_number": str(booking_id or "-"),
            "property_name": unit_type.name if unit_type else "订单关联房源",
            "move_in_date": booking.scheduled_date if booking and booking.scheduled_date else "待确认",
            "tenancy_months": booking.lease_months if booking else 0,
            "amount": amount,
            "status": booking.status.value if booking else "待确认",
            "payment_deadline": deadline,
            "order_url": order_url,
            "action_label": notification_action_label(event_type, recipient.role),
            "support_email": get_settings().support_email,
        }
        from app.services.email_service import EmailService

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                result = await EmailService().send_with_template(recipient.email, title, "order_event", context)
                if result.get("status") == "sent":
                    logger.info("订单邮件已投递 attempt=%s user_id=%s booking_id=%s", attempt, user_id, booking_id)
                    return
                logger.warning("订单邮件未投递 attempt=%s user_id=%s reason=%s", attempt, user_id, result.get("reason"))
                return
            except Exception as exc:
                last_error = exc
                logger.warning("订单邮件投递失败 attempt=%s user_id=%s booking_id=%s", attempt, user_id, booking_id, exc_info=True)
        logger.error("订单邮件最终投递失败 user_id=%s booking_id=%s error=%s", user_id, booking_id, last_error)

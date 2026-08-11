"""开发环境订单通知模拟调度服务，不修改订单或支付状态。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.booking import Booking
from app.models.contract import Contract
from app.models.notification import Notification, NotificationOutbox, NotificationOutboxStatus, NotificationType
from app.models.payment import Payment
from app.models.user import User, UserRole
from app.services.notification_link_service import notification_action_label, notification_target

logger = logging.getLogger(__name__)


EVENT_TITLES = {
    "PAYMENT_SUCCEEDED": "预订金支付成功，订单正在审核",
    "PAYMENT_FAILED": "预订金支付失败，请重新尝试",
    "PAYMENT_EXPIRING_3H": "预订金即将截止，请尽快支付",
    "CONTRACT_SENT": "合同已发送，请查阅并签署",
    "CONTRACT_EXPIRING_12H": "合同签署即将截止",
    "CONTRACT_SIGNED": "已完成预订",
    "BOOKING_SUCCEEDED": "预订成功",
    "BOOKING_FAILED_OR_CANCELLED": "订单已取消或未通过",
    "REFUND_STARTED": "预订金退款已发起",
    "REFUND_COMPLETED": "预订金已原路退还",
    "REFUND_FAILED": "退款处理失败",
    "ORDER_EXCEPTION": "订单需要人工处理",
    "ADMIN_CONTRACT_CONFIRMATION_REQUIRED": "新支付订单待确认合同",
}

ALL_EVENTS = frozenset(EVENT_TITLES)
ALL_CHANNELS = ("IN_APP", "EMAIL", "SMS")


def _masked(value: str | None, keep: int = 3) -> str:
    if not value:
        return "未提供"
    if "@" in value:
        name, domain = value.split("@", 1)
        return f"{name[:1]}***@{domain}"
    return f"{value[:keep]}****{value[-2:]}" if len(value) > keep + 2 else "****"


@dataclass(frozen=True)
class DeliveryResult:
    recipient: str
    role: str
    channel: str
    status: str
    attempts: int
    sent_at: str
    detail: str


class NotificationSimulationService:
    """复用通知表和 outbox 作为演示记录；外部通道永远不影响核心事务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _recipients(self, booking: Booking, event_type: str) -> list[User]:
        users: dict[int, User] = {}
        tenant = await self.session.get(User, booking.user_id)
        if tenant:
            users[tenant.id] = tenant
        if event_type in {"PAYMENT_SUCCEEDED", "BOOKING_SUCCEEDED", "CONTRACT_SIGNED", "ORDER_EXCEPTION", "REFUND_FAILED", "ADMIN_CONTRACT_CONFIRMATION_REQUIRED"}:
            if booking.bm_id:
                bm = await self.session.get(User, booking.bm_id)
                if bm:
                    users[bm.id] = bm
            admins = await self.session.scalars(select(User).where(User.role == UserRole.admin))
            users.update({admin.id: admin for admin in admins})
        return list(users.values())

    async def dispatch(self, booking: Booking, event_type: str, outcome: str) -> list[DeliveryResult]:
        if event_type not in ALL_EVENTS:
            raise ValueError("不支持的通知事件")
        if outcome not in {"success", "retry_success", "failed"}:
            raise ValueError("不支持的模拟结果")

        payment = await self.session.scalar(select(Payment).where(
            Payment.booking_id == booking.id, Payment.status == "success"
        ).order_by(Payment.paid_at.desc()))
        contract = await self.session.scalar(select(Contract).where(Contract.booking_id == booking.id).order_by(Contract.version.desc()))
        now = datetime.now(timezone.utc)
        amount = "CNY 0.00"
        if payment:
            amount = f"{payment.settlement_currency} {payment.settlement_amount_minor / 100:.2f}"
        if event_type in {"PAYMENT_SUCCEEDED", "ADMIN_CONTRACT_CONFIRMATION_REQUIRED"} and payment and payment.paid_at:
            deadline = (payment.paid_at + timedelta(days=3)).isoformat()
        elif event_type == "CONTRACT_EXPIRING_12H" and contract and contract.status == "generated" and contract.generated_at:
            deadline = (contract.generated_at + timedelta(days=7)).isoformat()
        else:
            deadline = booking.payment_expires_at.isoformat() if booking.payment_expires_at else "以订单详情显示的截止时间为准"
        results: list[DeliveryResult] = []
        for recipient in await self._recipients(booking, event_type):
            is_manager = recipient.role in {UserRole.admin, UserRole.landlord}
            # 同一事件的站内信与邮件共用可信内部目标，避免渠道跳转不一致。
            target = notification_target(event_type, recipient.role, booking.id)
            order_url = f"{get_settings().frontend_url.rstrip('/')}{target}"
            title = EVENT_TITLES[event_type]
            body = (
                f"订单【{booking.id}】事件：{title}。已付/应付预订金：{amount}。"
                f"该款项由平台收取以协助预订房源，不属于房屋租金或公寓押金；"
                f"租约正常到期且符合退款条件后按原支付渠道退还。截止时间：{deadline}。"
            )
            for channel in ALL_CHANNELS:
                event_key = f"notification-sim:{booking.id}:{event_type}:{recipient.id}:{channel}"
                existing = await self.session.scalar(select(NotificationOutbox).where(NotificationOutbox.event_key == event_key))
                if existing:
                    results.append(DeliveryResult(_masked(recipient.email or recipient.phone), recipient.role.value, channel, "deduplicated", existing.attempts, existing.sent_at.isoformat() if existing.sent_at else now.isoformat(), "同一订单、事件、收件人和渠道已发送"))
                    continue
                if channel == "IN_APP":
                    self.session.add(Notification(
                        user_id=recipient.id, type=NotificationType.system, title=title, content=body, body=body,
                        entity_type="order", entity_id=str(booking.id), order_id=str(payment.order_id if payment else booking.id),
                        agreement_id=contract.id if contract else None, unit_type_id=booking.unit_type_id,
                    ))
                    results.append(DeliveryResult(_masked(recipient.email or recipient.phone), recipient.role.value, channel, "sent", 1, now.isoformat(), target))
                    continue
                # 短信演示不能把没有手机号的情况伪装成已送达。由于现有 outbox
                # 状态枚举没有 skipped，保留结构化应用日志和接口结果说明即可，
                # 不新增数据库状态或字段。
                if channel == "SMS" and not recipient.phone:
                    logger.info(
                        "模拟短信跳过：收件人未提供手机号 booking=%s recipient=%s event=%s",
                        booking.id,
                        recipient.id,
                        event_type,
                    )
                    results.append(
                        DeliveryResult(
                            "未提供",
                            recipient.role.value,
                            channel,
                            "skipped",
                            0,
                            now.isoformat(),
                            "模拟发送未执行：收件人未提供手机号",
                        )
                    )
                    continue
                attempts = 2 if outcome == "retry_success" else (3 if outcome == "failed" else 1)
                sent = outcome != "failed"
                row = NotificationOutbox(
                    event_key=event_key, event_type=event_type, user_id=recipient.id, booking_id=booking.id,
                    channel=channel.lower(), template_version="sim-2026.1",
                    recipient_email=recipient.email if channel == "EMAIL" else None,
                    payload={"simulated": True, "recipient": _masked(recipient.email if channel == "EMAIL" else recipient.phone), "title": title, "body": body, "order_target": target, "event_type": event_type},
                    status=NotificationOutboxStatus.sent if sent else NotificationOutboxStatus.failed,
                    attempts=attempts, retryable=not sent, last_error=None if sent else "MOCK_DELIVERY_FAILED",
                    queued_at=now, sent_at=now if sent else None,
                )
                self.session.add(row)
                detail = "模拟发送；未调用真实服务商"
                if channel == "EMAIL" and sent and recipient.email:
                    try:
                        from app.services.email_service import EmailService

                        template_name = (
                            "payment_received"
                            if event_type == "PAYMENT_SUCCEEDED" and not is_manager
                            else "order_event"
                        )
                        template_context = {
                            "event_title": title,
                            "user_name": recipient.username,
                            "tenant_name": recipient.username,
                            "order_number": str(booking.id),
                            "property_name": "订单关联房源",
                            "property_city": "新加坡",
                            "move_in_date": booking.scheduled_date or "待确认",
                            "lease_start_date": booking.scheduled_date or "待确认",
                            "tenancy_months": booking.lease_months or 0,
                            "amount": amount,
                            "settlement_amount": f"{payment.settlement_amount_minor / 100:.2f}" if payment else "0.00",
                            "settlement_currency": payment.settlement_currency if payment else "CNY",
                            "payment_time": payment.paid_at.isoformat() if payment and payment.paid_at else "待确认",
                            "status": booking.status.value,
                            "payment_deadline": deadline,
                            "order_url": order_url,
                            "secure_order_url": order_url,
                            "action_label": notification_action_label(event_type, recipient.role),
                            "support_email": get_settings().support_email,
                        }
                        mail_result = await EmailService().send_with_template(
                            recipient.email,
                            title,
                            template_name,
                            template_context,
                        )
                        if mail_result.get("status") != "sent":
                            sent = False
                            row.status = NotificationOutboxStatus.failed
                            row.last_error = str(mail_result.get("reason") or "MOCK_EMAIL_SKIPPED")
                            detail = f"模拟邮件未投递：{row.last_error}"
                        else:
                            detail = "Mailpit 模拟邮件已投递"
                    except Exception as exc:
                        sent = False
                        row.status = NotificationOutboxStatus.failed
                        row.last_error = str(exc)
                        detail = "Mailpit 模拟邮件投递失败"
                        logger.exception("通知模拟邮件投递失败 booking=%s recipient=%s", booking.id, recipient.id)
                if not sent:
                    logger.error("通知模拟最终失败 event=%s booking=%s recipient=%s channel=%s", event_type, booking.id, recipient.id, channel)
                results.append(DeliveryResult(_masked(recipient.email if channel == "EMAIL" else recipient.phone), recipient.role.value, channel, "sent" if sent else "failed", attempts, now.isoformat(), detail))
        return results

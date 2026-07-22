"""通知服务 — 统一事件驱动的多渠道通知分发。

架构（对应文档第2节）：
  业务事件 → Outbox 写入（同事务）→ 渠道消费者 → 投递记录

关键原则：
  1. 浏览器跳转不能触发"支付成功"通知
  2. 仅服务端 Webhook 可确认支付
  3. 幂等键防重复发送
  4. 通知失败不回滚订单
  5. 消费前复核订单最新状态
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    Notification,
    NotificationDelivery,
    NotificationEventType,
    NotificationEntityType,
)

logger = logging.getLogger(__name__)

# ======================================================================
# 渠道矩阵 — 哪些事件通过哪些渠道发送（对应文档第4节）
# ======================================================================

ChannelMatrix = dict[str, dict[str, bool]]

# event_type → {tenant_email, tenant_sms, in_app, landlord_email}
CHANNEL_MATRIX: ChannelMatrix = {
    NotificationEventType.CONTRACT_SIGNED: {
        "tenant_email": True, "tenant_sms": False, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.PAYMENT_PENDING: {
        "tenant_email": True, "tenant_sms": False, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.PAYMENT_FAILED: {
        "tenant_email": True, "tenant_sms": True, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.PAYMENT_PROCESSING: {
        "tenant_email": False, "tenant_sms": False, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.PAYMENT_EXPIRING_IN_3_HOURS: {
        "tenant_email": True, "tenant_sms": True, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.PAYMENT_SUCCEEDED: {
        "tenant_email": True, "tenant_sms": True, "in_app": True, "landlord_email": True,
    },
    NotificationEventType.BOOKING_CONFIRMED: {
        "tenant_email": True, "tenant_sms": True, "in_app": True, "landlord_email": True,
    },
    NotificationEventType.ORDER_AUTO_CANCELLED: {
        "tenant_email": True, "tenant_sms": True, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.PAYMENT_REVIEW: {
        "tenant_email": True, "tenant_sms": False, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.REFUND_PENDING: {
        "tenant_email": True, "tenant_sms": False, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.REFUNDED: {
        "tenant_email": True, "tenant_sms": False, "in_app": True, "landlord_email": False,
    },
    NotificationEventType.CONTRACT_EXPIRING: {
        "tenant_email": True, "tenant_sms": False, "in_app": True, "landlord_email": False,
    },
}

# ======================================================================
# 通知标题和内容模板（站内消息用）
# ======================================================================

NOTIFICATION_TEMPLATES: dict[str, dict[str, str]] = {
    NotificationEventType.CONTRACT_SIGNED: {
        "title": "合同签署成功",
        "content": "您的租赁合同已签署成功，请尽快完成支付以确认预订。",
    },
    NotificationEventType.PAYMENT_PENDING: {
        "title": "订单等待支付",
        "content": "您的订单已生成，请在截止时间前完成支付，逾期订单将自动取消。",
    },
    NotificationEventType.PAYMENT_FAILED: {
        "title": "支付失败",
        "content": "您的支付未成功，请在截止时间前重新尝试支付，避免房源预留失效。",
    },
    NotificationEventType.PAYMENT_PROCESSING: {
        "title": "支付处理中",
        "content": "您的支付正在处理中，请耐心等待。支付确认后我们将立即通知您。",
    },
    NotificationEventType.PAYMENT_EXPIRING_IN_3_HOURS: {
        "title": "支付即将截止",
        "content": "您的订单将在约3小时后自动取消，请尽快完成支付以保留房源。",
    },
    NotificationEventType.PAYMENT_SUCCEEDED: {
        "title": "支付成功",
        "content": "您的支付已完成，预订已确认。祝您入住愉快！",
    },
    NotificationEventType.BOOKING_CONFIRMED: {
        "title": "预订已确认",
        "content": "您的租房预订已确认，请按时办理入住。",
    },
    NotificationEventType.ORDER_AUTO_CANCELLED: {
        "title": "订单已取消",
        "content": "您的订单因超过支付期限未完成付款，已自动取消，房源预留已释放。",
    },
    NotificationEventType.PAYMENT_REVIEW: {
        "title": "支付核对中",
        "content": "您的付款需要人工核对，我们会在核实后尽快通知您结果。",
    },
    NotificationEventType.REFUND_PENDING: {
        "title": "退款处理中",
        "content": "您的退款正在处理中，预计将在3-7个工作日内到账。",
    },
    NotificationEventType.REFUNDED: {
        "title": "退款成功",
        "content": "您的退款已成功处理，款项将退回原支付账户。",
    },
    NotificationEventType.CONTRACT_EXPIRING: {
        "title": "租期即将到期",
        "content": "您的租期临近结束，如需续租请在合同到期前联系房东协商。",
    },
}

# 房东通知模板
LANDLORD_NOTIFICATION_TEMPLATES = {
    NotificationEventType.PAYMENT_SUCCEEDED: {
        "title": "房屋出租成功",
        "content": "房源已成功出租，预订已确认。请查看订单详情并准备办理入住事宜。",
    },
    NotificationEventType.BOOKING_CONFIRMED: {
        "title": "预订确认通知",
        "content": "您的房源收到新的预订确认，请查看订单详情。",
    },
}

# 事件 → 邮件模板名映射
EVENT_EMAIL_TEMPLATE_MAP = {
    NotificationEventType.CONTRACT_SIGNED: "payment_created",
    NotificationEventType.PAYMENT_PENDING: "payment_created",
    NotificationEventType.PAYMENT_FAILED: "payment_failed",
    NotificationEventType.PAYMENT_EXPIRING_IN_3_HOURS: "payment_expiring",
    NotificationEventType.PAYMENT_SUCCEEDED: "payment_received",
    NotificationEventType.BOOKING_CONFIRMED: "booking_confirm",
    NotificationEventType.ORDER_AUTO_CANCELLED: "payment_expired",
    NotificationEventType.REFUNDED: "payment_received",
}


class NotificationService:
    """统一通知服务 — 事件驱动的多渠道分发。

    用法:
        svc = NotificationService(session)
        await svc.dispatch_event(
            event_type=NotificationEventType.PAYMENT_SUCCEEDED,
            user_id=tenant_id,
            order_id=order.id,
            property_id=room.id,
            landlord_id=room.landlord_id,
        )
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==================================================================
    # 核心分发方法
    # ==================================================================

    async def dispatch_event(
        self,
        event_type: str,
        user_id: int,
        *,
        order_id: int | None = None,
        property_id: int | None = None,
        agreement_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        landlord_id: int | None = None,
        context_extra: dict | None = None,
    ) -> dict:
        """根据事件类型分发到各渠道。

        Args:
            event_type: 业务事件类型（NotificationEventType 值）
            user_id: 租客用户ID（主接收人）
            order_id: 关联订单ID
            property_id: 关联房源ID
            agreement_id: 关联合同ID
            entity_type: 实体类型
            entity_id: 实体ID
            landlord_id: 房东用户ID（需要房东通知时必填）
            context_extra: 额外上下文（用于模板变量）

        Returns:
            {
                "notification_id": int | None,
                "delivery_ids": [int, ...],
                "channels_sent": ["in_app", "email", ...],
                "skipped": [{"channel": "sms", "reason": "..."}],
            }
        """
        matrix = CHANNEL_MATRIX.get(event_type, {})
        template = NOTIFICATION_TEMPLATES.get(event_type, {})
        result = {"notification_id": None, "delivery_ids": [], "channels_sent": [], "skipped": []}

        # ── 1. 站内通知（始终创建）────────────────────────────
        if matrix.get("in_app", True):
            notification = await self._create_in_app_notification(
                user_id=user_id,
                event_type=event_type,
                title=template.get("title", event_type),
                content=template.get("content", ""),
                order_id=order_id,
                property_id=property_id,
                agreement_id=agreement_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            result["notification_id"] = notification.id
            result["channels_sent"].append("in_app")

            # 房东站内通知
            if landlord_id and matrix.get("landlord_email", False):
                landlord_tpl = LANDLORD_NOTIFICATION_TEMPLATES.get(event_type)
                if landlord_tpl:
                    await self._create_in_app_notification(
                        user_id=landlord_id,
                        event_type=event_type,
                        title=landlord_tpl["title"],
                        content=landlord_tpl["content"],
                        order_id=order_id,
                        property_id=property_id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                    )

        # ── 2. 邮件 ──────────────────────────────────────────
        if matrix.get("tenant_email", False):
            delivery = await self._dispatch_email(
                user_id=user_id,
                event_type=event_type,
                order_id=order_id,
                property_id=property_id,
                agreement_id=agreement_id,
                context_extra=context_extra,
            )
            if delivery:
                result["delivery_ids"].append(delivery.id)
                result["channels_sent"].append("email")
            else:
                result["skipped"].append({"channel": "email", "reason": "no email or skipped"})

            # 房东邮件
            if landlord_id and matrix.get("landlord_email", False):
                landlord_delivery = await self._dispatch_email(
                    user_id=landlord_id,
                    event_type=f"landlord_{event_type}",
                    order_id=order_id,
                    property_id=property_id,
                    is_landlord=True,
                    context_extra=context_extra,
                )
                if landlord_delivery:
                    result["delivery_ids"].append(landlord_delivery.id)

        # ── 3. 短信 ──────────────────────────────────────────
        if matrix.get("tenant_sms", False):
            delivery = await self._dispatch_sms(
                user_id=user_id,
                event_type=event_type,
                order_id=order_id,
                context_extra=context_extra,
            )
            if delivery:
                result["delivery_ids"].append(delivery.id)
                result["channels_sent"].append("sms")
            else:
                result["skipped"].append({"channel": "sms", "reason": "no phone or skipped"})

        return result

    # ==================================================================
    # 站内通知 CRUD
    # ==================================================================

    async def _create_in_app_notification(
        self,
        user_id: int,
        event_type: str,
        title: str,
        content: str,
        order_id: int | None = None,
        property_id: int | None = None,
        agreement_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> Notification:
        """创建站内消息记录。"""
        notification = Notification(
            user_id=user_id,
            type=event_type,
            title=title,
            content=content,
            order_id=order_id,
            property_id=property_id,
            agreement_id=agreement_id,
            entity_type=entity_type or self._infer_entity_type(event_type),
            entity_id=entity_id or str(order_id) if order_id else None,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    # ==================================================================
    # 邮件分发
    # ==================================================================

    async def _dispatch_email(
        self,
        user_id: int,
        event_type: str,
        order_id: int | None = None,
        property_id: int | None = None,
        agreement_id: str | None = None,
        is_landlord: bool = False,
        context_extra: dict | None = None,
    ) -> NotificationDelivery | None:
        """写入邮件投递记录并触发 Celery 任务。"""
        idempotency_key = self._build_idempotency_key(event_type, user_id, order_id, "email")

        # 幂等检查
        existing = await self._check_idempotency(idempotency_key)
        if existing:
            logger.info("邮件幂等跳过: %s", idempotency_key)
            return None

        delivery = await self._create_delivery(
            user_id=user_id,
            event_type=event_type,
            channel="email",
            idempotency_key=idempotency_key,
            order_id=order_id,
        )

        # 触发 Celery 任务
        try:
            from app.tasks.notification_tasks import send_email_notification_with_template

            template_name = EVENT_EMAIL_TEMPLATE_MAP.get(event_type, "payment_created")
            subject = self._get_email_subject(event_type, is_landlord)

            ctx = dict(context_extra or {})
            ctx.setdefault("order_id", order_id)
            ctx.setdefault("property_id", property_id)

            send_email_notification_with_template.delay(
                user_id=user_id,
                subject=subject,
                template_name=template_name,
                context=ctx,
            )
            logger.info("邮件任务已入队: user=%s event=%s template=%s", user_id, event_type, template_name)
        except Exception as exc:
            logger.warning("邮件任务入队失败: %s", exc)

        return delivery

    # ==================================================================
    # 短信分发
    # ==================================================================

    async def _dispatch_sms(
        self,
        user_id: int,
        event_type: str,
        order_id: int | None = None,
        context_extra: dict | None = None,
    ) -> NotificationDelivery | None:
        """写入短信投递记录并触发 Celery 任务。"""
        idempotency_key = self._build_idempotency_key(event_type, user_id, order_id, "sms")

        existing = await self._check_idempotency(idempotency_key)
        if existing:
            logger.info("短信幂等跳过: %s", idempotency_key)
            return None

        delivery = await self._create_delivery(
            user_id=user_id,
            event_type=event_type,
            channel="sms",
            idempotency_key=idempotency_key,
            order_id=order_id,
        )

        try:
            from app.tasks.notification_tasks import send_sms_notification

            send_sms_notification.delay(
                user_id=user_id,
                notification_type=event_type,
                title=NOTIFICATION_TEMPLATES.get(event_type, {}).get("title", ""),
                content=self._get_sms_content(event_type, context_extra),
            )
            logger.info("短信任务已入队: user=%s event=%s", user_id, event_type)
        except Exception as exc:
            logger.warning("短信任务入队失败: %s", exc)

        return delivery

    # ==================================================================
    # 投递记录管理
    # ==================================================================

    async def _create_delivery(
        self,
        user_id: int,
        event_type: str,
        channel: str,
        idempotency_key: str,
        order_id: int | None = None,
    ) -> NotificationDelivery:
        """创建投递记录（queued 状态）。"""
        delivery = NotificationDelivery(
            user_id=user_id,
            event_type=event_type,
            channel=channel,
            idempotency_key=idempotency_key,
            order_id=order_id,
            status="queued",
            queued_at=datetime.now(timezone.utc),
        )
        self.session.add(delivery)
        await self.session.commit()
        await self.session.refresh(delivery)
        return delivery

    async def _check_idempotency(self, idempotency_key: str) -> NotificationDelivery | None:
        """检查幂等键是否已存在。"""
        stmt = select(NotificationDelivery).where(
            NotificationDelivery.idempotency_key == idempotency_key
        )
        result = await self.session.scalars(stmt)
        return result.first()

    async def update_delivery_status(
        self,
        delivery_id: int,
        status: str,
        provider_message_id: str | None = None,
        error_code: str | None = None,
    ) -> NotificationDelivery | None:
        """更新投递状态。"""
        delivery = await self.session.get(NotificationDelivery, delivery_id)
        if not delivery:
            return None

        delivery.status = status
        delivery.attempt_count += 1
        if provider_message_id:
            delivery.provider_message_id = provider_message_id
        if error_code:
            delivery.last_error_code = error_code

        now = datetime.now(timezone.utc)
        if status == "sent":
            delivery.sent_at = now
        elif status == "delivered":
            delivery.delivered_at = now
        elif status == "failed":
            delivery.failed_at = now

        await self.session.commit()
        return delivery

    # ==================================================================
    # 站内通知查询
    # ==================================================================

    async def list_by_user(
        self, user_id: int, filter_type: str | None = None, entity_type: str | None = None
    ) -> list[Notification]:
        """获取用户通知列表，支持筛选。"""
        conditions = [Notification.user_id == user_id]

        if filter_type == "unread":
            conditions.append(Notification.is_read == False)
        if entity_type:
            conditions.append(Notification.entity_type == entity_type)

        stmt = (
            select(Notification)
            .where(and_(*conditions))
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

    async def mark_all_read(self, user_id: int) -> int:
        """标记所有未读为已读，返回影响行数。"""
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_unread_count(self, user_id: int) -> int:
        stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_delivery(self, delivery_id: int) -> NotificationDelivery | None:
        return await self.session.get(NotificationDelivery, delivery_id)

    async def list_deliveries_by_order(
        self, order_id: int
    ) -> list[NotificationDelivery]:
        stmt = (
            select(NotificationDelivery)
            .where(NotificationDelivery.order_id == order_id)
            .order_by(NotificationDelivery.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    # ==================================================================
    # 辅助方法
    # ==================================================================

    @staticmethod
    def _build_idempotency_key(
        event_type: str, user_id: int, entity_id: int | None, channel: str
    ) -> str:
        """构建幂等键。

        格式: {event_type}:{user_id}:{entity_id}:{channel}
        特殊: 支付截止三小时提醒携带 expires_at 防跨周期重复
        """
        eid = entity_id or 0
        return f"{event_type}:{user_id}:{eid}:{channel}"

    @staticmethod
    def _infer_entity_type(event_type: str) -> str:
        """从事件类型推断实体类型。"""
        if "payment" in event_type or "refund" in event_type:
            return NotificationEntityType.payment
        if "contract" in event_type:
            return NotificationEntityType.contract
        if "booking" in event_type or "order" in event_type:
            return NotificationEntityType.order
        return NotificationEntityType.system

    @staticmethod
    def _get_email_subject(event_type: str, is_landlord: bool = False) -> str:
        """邮件主题。"""
        subjects = {
            NotificationEventType.CONTRACT_SIGNED: "您的租赁合同已签署 - 请完成支付",
            NotificationEventType.PAYMENT_PENDING: "您的订单已生成 - 请尽快支付",
            NotificationEventType.PAYMENT_FAILED: "支付未成功 - 请重新尝试",
            NotificationEventType.PAYMENT_PROCESSING: "支付处理中",
            NotificationEventType.PAYMENT_EXPIRING_IN_3_HOURS: "【支付即将截止】您的订单将在3小时后自动取消",
            NotificationEventType.PAYMENT_SUCCEEDED: "支付成功 - 预订已确认",
            NotificationEventType.BOOKING_CONFIRMED: "预订已确认 - 欢迎入住",
            NotificationEventType.ORDER_AUTO_CANCELLED: "订单已自动取消",
            NotificationEventType.PAYMENT_REVIEW: "付款核对中",
            NotificationEventType.REFUND_PENDING: "退款处理中",
            NotificationEventType.REFUNDED: "退款成功",
            NotificationEventType.CONTRACT_EXPIRING: "租期即将到期",
        }
        if is_landlord:
            landlord_subjects = {
                NotificationEventType.PAYMENT_SUCCEEDED: "房屋出租成功 - 请查看订单",
                NotificationEventType.BOOKING_CONFIRMED: "新房源预订确认",
            }
            return landlord_subjects.get(event_type, subjects.get(event_type, f"通知: {event_type}"))
        return subjects.get(event_type, f"通知: {event_type}")

    @staticmethod
    def _get_sms_content(event_type: str, context_extra: dict | None = None) -> str:
        """短信内容（简短版）。"""
        ctx = context_extra or {}
        templates = {
            NotificationEventType.PAYMENT_SUCCEEDED: (
                f"【租房平台】您的预订已确认。订单{ctx.get('order_number', '')}，"
                f"入住日期：{ctx.get('lease_start_date', '')}，已支付{ctx.get('amount', '')}{ctx.get('currency', '')}。"
            ),
            NotificationEventType.PAYMENT_FAILED: (
                f"【租房平台】订单{ctx.get('order_number', '')}支付未成功。"
                f"请在{ctx.get('expires_at', '')}前重新支付，避免房源预留失效。"
            ),
            NotificationEventType.PAYMENT_EXPIRING_IN_3_HOURS: (
                f"【租房平台】订单{ctx.get('order_number', '')}尚未支付，将在约3小时后自动取消。"
                f"请在{ctx.get('expires_at', '')}前完成支付。"
            ),
            NotificationEventType.ORDER_AUTO_CANCELLED: (
                f"【租房平台】订单{ctx.get('order_number', '')}因超过支付期限未完成付款，"
                f"已自动取消，房源预留已释放。"
            ),
        }
        return templates.get(event_type, f"【租房平台】您有一条新通知：{event_type}")

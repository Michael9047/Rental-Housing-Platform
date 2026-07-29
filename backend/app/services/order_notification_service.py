"""订单/支付相关的通知入队服务。"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.booking import Booking
from app.models.contract import Contract
from app.models.payment import Payment
from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)

EVENT_TEMPLATES = {
    "payment_succeeded": {
        "title": "支付成功",
        "content_tpl": "订单 #{booking_id} 已支付成功，金额 {amount}。合同已生效。",
    },
    "payment_failed": {
        "title": "支付失败",
        "content_tpl": "订单 #{booking_id} 支付未成功，可在有效期内重试。",
    },
    "payment_expired": {
        "title": "支付超时",
        "content_tpl": "订单 #{booking_id} 超过24小时未完成支付，预订已失效。",
    },
    "contract_resign_required": {
        "title": "合同需重新签署",
        "content_tpl": "订单 #{booking_id} 合同已更新为版本 v{version}，请重新签署。",
    },
    "late_payment_review": {
        "title": "迟到付款待核对",
        "content_tpl": "订单 #{booking_id} 过期后收到付款，需人工核对。",
    },
    "refund_succeeded": {
        "title": "退款成功",
        "content_tpl": "订单 #{booking_id} 退款已处理。",
    },
    "refund_failed": {
        "title": "退款失败",
        "content_tpl": "订单 #{booking_id} 退款处理失败，请查看详情。",
    },
}


class OrderNotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        event: str,
        booking: Booking,
        *,
        payment: Payment | None = None,
        contract: Contract | None = None,
        discriminator: str = "",
    ) -> None:
        """为租客创建通知记录。"""
        template = EVENT_TEMPLATES.get(event)
        if not template:
            logger.warning("Unknown notification event: %s", event)
            return

        amount_str = ""
        if payment:
            amount_str = f"{payment.settlement_currency} {payment.settlement_amount_minor / 100:.2f}"

        content = template["content_tpl"].format(
            booking_id=booking.id,
            amount=amount_str,
            version=discriminator,
        )

        notification = Notification(
            user_id=booking.tenant_id,
            type=NotificationType.system,
            title=template["title"],
            content=content,
        )
        self.session.add(notification)
        await self.session.flush()

    async def enqueue_landlord_booking_confirmed(
        self, booking: Booking, payment: Payment
    ) -> None:
        """通知房东预订已支付确认。"""
        content = (
            f"房源 #{booking.property_id} 已被预订（订单 #{booking.id}），"
            f"支付金额 {payment.settlement_currency} {payment.settlement_amount_minor / 100:.2f}。"
        )
        notification = Notification(
            user_id=booking.landlord_id,
            type=NotificationType.booking_created,
            title="新预订已支付确认",
            content=content,
        )
        self.session.add(notification)
        await self.session.flush()

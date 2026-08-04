"""订单业务事件、站内通知与邮件 outbox 的统一入口。"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.booking import Booking
from app.models.contract import Contract
from app.models.notification import Notification, NotificationOutbox, NotificationOutboxStatus, NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.property import Property
from app.models.user import User, UserRole

TEMPLATE_VERSION = "order-event-2026.1"
TITLES = {
    "LANDLORD_BOOKING_CONFIRMED": "【房屋已成功预订】订单 {order_number} / Property Booking Confirmed",
    "contract_signed": "合同签署成功，请完成支付",
    "payment_succeeded": "支付成功，预订已确认",
    "payment_failed": "支付未成功",
    "payment_processing_delayed": "支付结果仍在确认中",
    "payment_reminder_12h": "支付截止时间提醒（剩余12小时）",
    "payment_reminder_1h": "支付截止时间提醒（剩余1小时）",
    "payment_expired": "订单已自动取消",
    "late_payment_review": "迟到付款正在核对或退款",
    "refund_succeeded": "退款成功",
    "refund_failed": "退款处理失败",
    "contract_resign_required": "合同版本已更新，请重新签署",
}


class OrderNotificationService:
    def __init__(self, session: AsyncSession) -> None: self.session = session

    async def enqueue(self, event_type: str, booking: Booking, *, payment: Payment | None = None, contract: Contract | None = None, discriminator: str = "1") -> NotificationOutbox | None:
        event_key = f"order:{booking.id}:{event_type}:{discriminator}"
        existing = await self.session.scalar(select(NotificationOutbox).where(NotificationOutbox.event_key == event_key))
        if existing: return None
        user = await self.session.get(User, booking.tenant_id); property_obj = await self.session.get(Property, booking.property_id)
        if not user or not property_obj: return None
        if contract is None: contract = await self.session.scalar(select(Contract).where(Contract.booking_id == booking.id).order_by(Contract.version.desc()))
        pricing = (booking.application_data or {}).get("pricing_snapshot") or {}; option = next((x for x in pricing.get("options",[]) if x.get("months")==booking.lease_months),None)
        local = ((option or {}).get("prices") or {}).get("amount_due_now",{}).get("local",{})
        currency = payment.settlement_currency if payment else local.get("currency","CNY"); minor = payment.settlement_amount_minor if payment else int(local.get("minor_units",0))
        amount = f"{currency} {(Decimal(minor)/Decimal(100)):.2f}"
        title = TITLES[event_type]
        status = booking.status.value if hasattr(booking.status,"value") else str(booking.status)
        payload = {"user_name":user.username,"order_number":str(booking.id),"property_name":property_obj.title,"property_address":property_obj.address,"move_in_date":booking.scheduled_date or "待确认","tenancy_months":booking.lease_months or 0,"amount":amount,"status":status,"payment_deadline":booking.payment_expires_at.isoformat() if booking.payment_expires_at else None,"order_url":f"{get_settings().frontend_url}/booking/order/{booking.id}/payment-status","support_email":get_settings().support_email,"contract_number":contract.agreement_number if contract else None}
        notification = Notification(user_id=user.id,type=NotificationType.system,title=title,content=f"订单 #{booking.id}：{title}", body=f"订单 #{booking.id}：{title}", entity_type="order", entity_id=str(booking.id), order_id=str(getattr(payment, "order_id", None) or booking.id), agreement_id=str(contract.id) if contract else None, property_id=booking.property_id)
        outbox = NotificationOutbox(event_key=event_key,event_type=event_type,user_id=user.id,booking_id=booking.id,channel="email",template_version=TEMPLATE_VERSION,payload=payload,status=NotificationOutboxStatus.pending,next_attempt_at=datetime.now(timezone.utc))
        self.session.add_all([notification,outbox]); return outbox

    async def enqueue_landlord_booking_confirmed(
        self,
        booking: Booking,
        payment: Payment,
        *,
        contract: Contract | None = None,
    ) -> NotificationOutbox | None:
        """仅为已由有效 webhook 确认的付款创建一次房东通知。"""
        booking_status = booking.status.value if hasattr(booking.status, "value") else str(booking.status)
        payment_status = payment.status.value if hasattr(payment.status, "value") else str(payment.status)
        if booking_status != "paid" or payment_status != PaymentStatus.success.value or not payment.paid_at:
            return None

        event_key = f"landlord-booking-confirmed:{booking.id}:{payment.id}"
        existing = await self.session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.event_key == event_key)
        )
        if existing:
            return None

        property_obj = await self.session.get(Property, booking.property_id)
        if not property_obj:
            return None
        landlord = await self.session.get(User, property_obj.landlord_id)
        if not landlord:
            return None
        if contract is None:
            contract = await self.session.scalar(
                select(Contract)
                .where(Contract.booking_id == booking.id)
                .order_by(Contract.version.desc())
            )

        snapshot = payment.snapshot or {}
        minor_exponent = 2
        settlement_amount = f"{payment.settlement_currency} {(Decimal(payment.settlement_amount_minor) / (Decimal(10) ** minor_exponent)):.2f}"
        cny_reference = f"CNY {(Decimal(payment.cny_reference_amount_minor) / Decimal(100)):.2f}"
        property_reference = snapshot.get("fees", {}).get("current_total", {})
        property_reference_amount = (
            f"{property_reference.get('currency', payment.property_currency)} {property_reference.get('decimal')}"
            if property_reference.get("decimal") is not None
            else None
        )
        title = TITLES["LANDLORD_BOOKING_CONFIRMED"].format(order_number=booking.id)
        payload = {
            "event_title": title,
            "user_name": landlord.username,
            "order_number": str(booking.id),
            "property_id": property_obj.id,
            "property_name": property_obj.title,
            "property_address": property_obj.address,
            "room_type": property_obj.property_type.value if hasattr(property_obj.property_type, "value") else str(property_obj.property_type),
            "move_in_date": snapshot.get("commencement_date") or booking.scheduled_date,
            "expiry_date": snapshot.get("expiry_date"),
            "tenancy_months": snapshot.get("tenancy_months") or booking.lease_months,
            "amount": settlement_amount,
            "settlement_amount": settlement_amount,
            "cny_reference_amount": cny_reference,
            "property_reference_amount": property_reference_amount,
            "paid_at": payment.paid_at.isoformat(),
            "contract_number": snapshot.get("agreement_number") or (contract.agreement_number if contract else None),
            "tenant_name": snapshot.get("tenant_name") or "租客",
            "status": "paid",
            "payment_deadline": "不适用",
            "order_url": f"{get_settings().frontend_url}/bookings/landlord?order_id={booking.id}",
            "property_manage_url": f"{get_settings().frontend_url}/property/manage?property_id={property_obj.id}",
            "support_email": get_settings().support_email,
        }
        notification = Notification(
            user_id=landlord.id,
            type=NotificationType.booking_completed,
            title=title,
            content=f"房源“{property_obj.title}”已成功预订，订单 #{booking.id}。",
            body=f"房源“{property_obj.title}”已成功预订，订单 #{booking.id}。",
            entity_type="order", entity_id=str(booking.id), order_id=str(payment.order_id),
            agreement_id=str(contract.id) if contract else None, property_id=booking.property_id,
        )

        verified_email = landlord.email if landlord.email and getattr(landlord, "email_verified", False) else None
        now = datetime.now(timezone.utc)
        outbox = NotificationOutbox(
            event_key=event_key,
            event_type="LANDLORD_BOOKING_CONFIRMED",
            user_id=landlord.id,
            booking_id=booking.id,
            channel="email",
            template_version="landlord-2026.1",
            recipient_email=verified_email,
            payload=payload,
            status=NotificationOutboxStatus.pending if verified_email else NotificationOutboxStatus.failed,
            retryable=bool(verified_email),
            last_error=None if verified_email else "LANDLORD_EMAIL_NOT_VERIFIED",
            queued_at=now,
            next_attempt_at=now if verified_email else None,
        )
        self.session.add_all([notification, outbox])

        if not verified_email:
            admins = await self.session.scalars(select(User).where(User.role == UserRole.admin))
            for admin in admins:
                self.session.add(Notification(
                    user_id=admin.id,
                    type=NotificationType.system,
                    title="房东预订通知投递失败",
                    content=f"订单 #{booking.id} 的房东账户缺少已验证邮箱，请人工处理。",
                ))
        return outbox

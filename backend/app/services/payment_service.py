"""从订单价格快照创建支付单并以验签 webhook 原子确认结果。"""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.audit_log import AuditLog
from app.models.contract import Contract, ContractSignature
from app.models.payment import Payment, PaymentStatus, PaymentWebhookEvent
from app.models.property import Property, PropertyStatus
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.services.payment_provider import MockHostedPaymentProvider, PaymentMethod, PaymentRequest, get_test_provider
from app.services.lease_pricing_service import LeasePricingService
from app.services.order_notification_service import OrderNotificationService


class PaymentOrderService:
    def __init__(self, session: AsyncSession, provider=None) -> None:
        self.session = session
        self.provider = provider or MockHostedPaymentProvider()

    ALLOWED_TRANSITIONS = {
        BookingStatus.contract_signed: {BookingStatus.payment_pending},
        BookingStatus.payment_pending: {BookingStatus.payment_processing, BookingStatus.paid, BookingStatus.payment_failed, BookingStatus.payment_expired},
        BookingStatus.payment_processing: {BookingStatus.paid, BookingStatus.payment_failed, BookingStatus.payment_expired, BookingStatus.payment_review},
        BookingStatus.payment_failed: {BookingStatus.payment_pending, BookingStatus.paid, BookingStatus.payment_expired},
        BookingStatus.payment_expired: {BookingStatus.payment_review, BookingStatus.refund_pending},
        BookingStatus.payment_review: {BookingStatus.refund_pending, BookingStatus.paid, BookingStatus.cancelled},
        BookingStatus.refund_pending: {BookingStatus.refunded},
    }

    def _transition(self, booking: Booking, target: BookingStatus, *, reason: str, actor_user_id: int | None = None, payment_id: str | None = None) -> None:
        """仅由后端执行状态转换，并在同一事务写入审计日志。"""
        source = booking.status
        if source == target:
            return
        if target not in self.ALLOWED_TRANSITIONS.get(source, set()):
            raise RuntimeError(f"不允许的订单状态转换：{source.value} → {target.value}")
        booking.status = target
        self.session.add(AuditLog(user_id=actor_user_id, action="booking_payment_status_changed", resource_type="booking", resource_id=booking.id, details={"from": source.value, "to": target.value, "reason": reason, "payment_id": payment_id}))

    def _notify(self, user_id: int, kind: NotificationType, title: str, content: str) -> None:
        self.session.add(Notification(user_id=user_id, type=kind, title=title, content=content))

    @staticmethod
    def webhook_target(status: BookingStatus, event_status: str, now: datetime, expires_at: datetime) -> BookingStatus:
        """将验签后的服务商结果映射为订单状态，便于独立测试边界时间。"""
        if event_status == "succeeded":
            if status == BookingStatus.payment_expired or now >= expires_at:
                return BookingStatus.payment_review
            return BookingStatus.paid
        return BookingStatus.payment_expired if status == BookingStatus.payment_expired else BookingStatus.payment_failed

    @staticmethod
    def should_expire(status: BookingStatus, provider_state: str | None, payment_succeeded: bool) -> bool:
        if payment_succeeded or status in {BookingStatus.paid, BookingStatus.payment_expired, BookingStatus.cancelled, BookingStatus.refund_pending, BookingStatus.refunded, BookingStatus.payment_review}:
            return False
        if status == BookingStatus.payment_processing and provider_state in {"processing", "succeeded"}:
            return False
        return status in {BookingStatus.payment_pending, BookingStatus.payment_processing, BookingStatus.payment_failed}

    @staticmethod
    def release_inventory(booking: Booking) -> None:
        """释放该订单的临时库存预留，不改变已支付房源的出租状态。"""
        booking.inventory_reserved = False

    @staticmethod
    def _price_snapshot(booking: Booking, contract: Contract, property_obj: Property, tenant_name: str) -> tuple[dict, dict]:
        pricing = (booking.application_data or {}).get("pricing_snapshot") or {}
        option = next((x for x in pricing.get("options", []) if x.get("months") == booking.lease_months), None)
        if not option:
            raise ValueError("订单缺少不可变价格快照")
        prices = option["prices"]
        snapshot = {
            "order_number": str(booking.id), "property_id": booking.property_id,
            "property_name": property_obj.title, "property_address": property_obj.address,
            "commencement_date": booking.scheduled_date, "expiry_date": option["end_date"],
            "tenancy_months": booking.lease_months, "tenant_name": tenant_name,
            "agreement_id": contract.id, "agreement_number": contract.agreement_number,
            "agreement_version": contract.version, "agreement_content_hash": contract.content_hash,
            "fees": {"deposit": prices["deposit"]["local"], "service_fee": prices["service_fee"]["local"], "tax": {"currency": pricing["local_currency"], "minor_units": 0, "minor_unit_exponent": 2, "decimal": "0.00"}, "current_total": prices["amount_due_now"]["local"]},
        }
        return pricing, snapshot

    async def _ensure_availability(self, booking: Booking) -> None:
        """支付前按订单日期区间复核同一房源的有效占用。"""
        if not booking.scheduled_date or not booking.lease_months:
            raise RuntimeError("订单缺少有效入住日期或租期")
        start = datetime.fromisoformat(booking.scheduled_date).date()
        end = LeasePricingService.add_calendar_months(start, booking.lease_months)
        candidates = await self.session.scalars(select(Booking).where(
            Booking.property_id == booking.property_id,
            Booking.id != booking.id,
            Booking.status.in_([BookingStatus.contract_signed, BookingStatus.payment_pending, BookingStatus.completed]),
        ))
        for other in candidates:
            if not other.scheduled_date or not other.lease_months:
                continue
            other_start = datetime.fromisoformat(other.scheduled_date).date()
            other_end = LeasePricingService.add_calendar_months(other_start, other.lease_months)
            if start < other_end and other_start < end:
                raise RuntimeError("房源在所选租期内已存在冲突订单")

    async def create(self, booking_id: int, user_id: int, idempotency_key: str, tenant_name: str, payment_method: PaymentMethod = PaymentMethod.CARD_CHECKOUT) -> Payment:
        from app.core.config import get_settings
        if get_settings().environment.lower() == "production" and get_settings().payment_provider == "mock_hosted":
            raise RuntimeError("生产环境禁止使用本地模拟支付服务商")
        by_key = await self.session.scalar(select(Payment).options(selectinload(Payment.booking)).where(Payment.idempotency_key == idempotency_key))
        if by_key:
            if by_key.booking_id != booking_id or by_key.user_id != user_id: raise PermissionError("幂等键已用于其他订单")
            return by_key
        booking = await self.session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
        if not booking: raise LookupError("订单不存在")
        if booking.tenant_id != user_id: raise PermissionError("只能支付本人的订单")
        active = await self.session.scalar(select(Payment).where(Payment.booking_id == booking_id, Payment.status.in_([PaymentStatus.pending, PaymentStatus.processing])).order_by(Payment.created_at.desc()))
        if active:
            active.booking = booking
            return active
        now = datetime.now(timezone.utc)
        if booking.payment_expires_at and booking.payment_expires_at <= now: raise TimeoutError("支付订单已超过24小时有效期")
        if booking.status == BookingStatus.payment_expired: raise RuntimeError("订单支付已过期，请重新发起预订")
        if booking.status not in {BookingStatus.contract_signed, BookingStatus.payment_pending, BookingStatus.payment_failed}: raise RuntimeError("必须先签署当前版本合同，且订单处于可付款状态")
        contract = await self.session.scalar(select(Contract).where(Contract.booking_id == booking.id, Contract.status == "signed").order_by(Contract.version.desc()))
        if not contract or not await self.session.scalar(select(ContractSignature).where(ContractSignature.agreement_id == contract.id, ContractSignature.tenant_user_id == user_id)):
            raise RuntimeError("未找到当前合同的有效租客签名")
        property_obj = await self.session.get(Property, booking.property_id)
        if not property_obj or property_obj.status != PropertyStatus.available: raise RuntimeError("房源当前不可支付预订")
        await self._ensure_availability(booking)
        pricing, snapshot = self._price_snapshot(booking, contract, property_obj, tenant_name)
        local = snapshot["fees"]["current_total"]
        cny = next(x for x in pricing["options"] if x.get("months") == booking.lease_months)["prices"]["amount_due_now"]["cny"]
        expires = booking.payment_expires_at or now + timedelta(hours=24)
        payment_attempt_id = str(uuid.uuid4())
        order_id = f"PAY-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:20].upper()}"
        self.provider = get_test_provider(payment_method)
        payment = Payment(id=payment_attempt_id, order_id=order_id, payment_attempt_id=payment_attempt_id, booking_id=booking.id, user_id=user_id, amount=local["minor_units"], out_trade_no=order_id, status=PaymentStatus.processing, payment_method=payment_method.value, settlement_currency=local["currency"], settlement_amount_minor=local["minor_units"], cny_reference_amount_minor=cny["minor_units"], property_currency=pricing["local_currency"], exchange_rate=Decimal(str(pricing["exchange_rate_to_cny"])), exchange_rate_source=pricing["exchange_rate_source"], exchange_rate_timestamp=datetime.fromisoformat(str(pricing["exchange_rate_at"]).replace("Z", "+00:00")), expires_at=expires, provider=self.provider.name, idempotency_key=idempotency_key, snapshot=snapshot)
        payment.booking = booking
        checkout = self.provider.create_payment(PaymentRequest(order_id=order_id,payment_attempt_id=payment_attempt_id,amount_minor=payment.settlement_amount_minor,settlement_currency=payment.settlement_currency,expires_at=expires.isoformat(),idempotency_key=idempotency_key,description=f"Booking {booking.id}"))
        payment.provider_payment_id, payment.provider_checkout_id, payment.checkout_url, payment.provider_merchant_account = checkout.provider_payment_id, checkout.provider_checkout_id, checkout.checkout_url, checkout.merchant_account
        self.session.add(payment)
        self._transition(booking, BookingStatus.payment_pending, reason="创建24小时支付订单", actor_user_id=user_id, payment_id=payment.id)
        booking.payment_expires_at = expires; booking.inventory_reserved = True
        self._transition(booking, BookingStatus.payment_processing, reason="支付服务商已创建托管收银台", actor_user_id=user_id, payment_id=payment.id)
        await self.session.commit(); await self.session.refresh(payment); payment.booking = booking
        return payment

    async def process_webhook(self, payload: bytes, signature: str) -> Payment:
        event = self.provider.verify_webhook(payload, signature)
        duplicate = await self.session.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.provider == self.provider.name, PaymentWebhookEvent.event_id == event.get("event_id")))
        payment = await self.session.scalar(select(Payment).where(Payment.provider_payment_id == event.get("provider_payment_id")))
        if not payment: raise LookupError("支付对象不存在")
        if duplicate: return payment
        booking = await self.session.scalar(select(Booking).where(Booking.id == payment.booking_id).with_for_update())
        payment = await self.session.scalar(select(Payment).where(Payment.id == payment.id).with_for_update())
        payment.booking = booking
        self.validate_event(event, payment)
        self.session.add(PaymentWebhookEvent(provider=self.provider.name, event_id=event["event_id"], payload_hash=hashlib.sha256(payload).hexdigest(), processed_at=datetime.now(timezone.utc)))
        target = self.webhook_target(booking.status, event.get("status", "failed"), datetime.now(timezone.utc), payment.expires_at)
        if event.get("status") == "succeeded":
            if target == BookingStatus.payment_review:
                payment.status, payment.trade_state, payment.trade_state_desc = PaymentStatus.review, "LATE_SUCCESS", "订单过期后收到成功付款，等待人工退款或核对"
                self._transition(booking, BookingStatus.payment_review, reason="过期后收到成功支付 webhook", payment_id=payment.id)
                self.release_inventory(booking)
                await OrderNotificationService(self.session).enqueue("late_payment_review", booking, payment=payment, discriminator=payment.id)
                admins = await self.session.scalars(select(User).where(User.role == UserRole.admin))
                for admin in admins:
                    self._notify(admin.id, NotificationType.system, "迟到付款待处理", f"订单 #{booking.id} 已过期后收到付款，请人工核对或退款。")
                await self.session.commit(); await self.session.refresh(payment)
                return payment
            property_obj = await self.session.scalar(select(Property).where(Property.id == booking.property_id).with_for_update())
            payment.status, payment.paid_at, payment.transaction_id, payment.trade_state = PaymentStatus.success, datetime.now(timezone.utc), event.get("transaction_id"), "SUCCESS"
            booking.deposit_status, booking.payment_transaction_id = "paid", payment.transaction_id
            self._transition(booking, BookingStatus.paid, reason="支付服务商有效成功 webhook", payment_id=payment.id)
            booking.inventory_reserved = False
            property_obj.status = PropertyStatus.rented
            await OrderNotificationService(self.session).enqueue("payment_succeeded", booking, payment=payment, discriminator=payment.id)
            await OrderNotificationService(self.session).enqueue_landlord_booking_confirmed(booking, payment)
        else:
            payment.status, payment.trade_state, payment.trade_state_desc = PaymentStatus.failed, "FAILED", "测试支付失败，可在有效期内重试"
            if booking.status == BookingStatus.payment_expired:
                await self.session.commit(); await self.session.refresh(payment)
                return payment
            self._transition(booking, BookingStatus.payment_failed, reason="支付服务商失败 webhook", payment_id=payment.id)
            await OrderNotificationService(self.session).enqueue("payment_failed", booking, payment=payment, discriminator=payment.id)
        await self.session.commit(); await self.session.refresh(payment)
        return payment

    async def expire_due_orders(self, now: datetime | None = None) -> dict[str, int]:
        """扫描到期订单；逐单加锁，确保与成功 webhook 竞争时只有一方生效。"""
        now = now or datetime.now(timezone.utc)
        ids = list(await self.session.scalars(select(Booking.id).where(
            Booking.payment_expires_at <= now,
            Booking.status.in_([BookingStatus.payment_pending, BookingStatus.payment_processing, BookingStatus.payment_failed]),
        )))
        expired = checked = 0
        for booking_id in ids:
            result = await self.expire_one(booking_id, now)
            checked += 1
            expired += int(result)
        return {"checked": checked, "expired": expired}

    async def expire_one(self, booking_id: int, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        booking = await self.session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
        if not booking or not booking.payment_expires_at or booking.payment_expires_at > now:
            return False
        payment = await self.session.scalar(select(Payment).where(Payment.booking_id == booking.id).order_by(Payment.created_at.desc()).with_for_update())
        payment_succeeded = bool(payment and payment.status == PaymentStatus.success)
        provider_state = None
        if booking.status == BookingStatus.payment_processing and payment:
            provider_state = self.provider.query_payment(payment.provider_payment_id or "")
            if provider_state in {"processing", "succeeded"}:
                self.session.add(AuditLog(user_id=None, action="payment_expiry_deferred", resource_type="booking", resource_id=booking.id, details={"provider_state": provider_state, "payment_id": payment.id}))
                await self.session.commit()
                return False
        if not self.should_expire(booking.status, provider_state, payment_succeeded):
            return False
        if payment:
            payment.status, payment.trade_state, payment.trade_state_desc = PaymentStatus.expired, "EXPIRED", "24小时内未完成付款"
        self._transition(booking, BookingStatus.payment_expired, reason="到期且服务商未确认成功", payment_id=payment.id if payment else None)
        self.release_inventory(booking)
        await OrderNotificationService(self.session).enqueue("payment_expired", booking, payment=payment, discriminator="24h")
        await self.session.commit()
        return True

    async def record_refund_result(self, booking_id: int, succeeded: bool, provider_event_id: str) -> None:
        """供未来退款 provider webhook 调用；不在此方法发起真实退款。"""
        booking = await self.session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
        if not booking or booking.status != BookingStatus.refund_pending:
            raise RuntimeError("订单不处于等待退款状态")
        payment = await self.session.scalar(select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc()).with_for_update())
        if succeeded:
            payment.status = PaymentStatus.refunded
            self._transition(booking, BookingStatus.refunded, reason="支付服务商确认退款成功", payment_id=payment.id)
            event = "refund_succeeded"
        else:
            event = "refund_failed"
            self.session.add(AuditLog(user_id=None, action="payment_refund_failed", resource_type="booking", resource_id=booking.id, details={"payment_id":payment.id,"provider_event_id":provider_event_id}))
        await OrderNotificationService(self.session).enqueue(event, booking, payment=payment, discriminator=provider_event_id)
        await self.session.commit()

    @staticmethod
    def validate_event(event: dict, payment: Payment) -> None:
        """逐项核对服务商事件，浏览器返回地址不参与支付判定。"""
        checks = {
            "merchant_account": payment.provider_merchant_account,
            "order_number": payment.out_trade_no,
            "currency": payment.settlement_currency,
            "amount_minor": payment.settlement_amount_minor,
            "provider_payment_id": payment.provider_payment_id,
        }
        if any(event.get(key) != value for key, value in checks.items()):
            raise ValueError("Webhook 商户、订单、金额、币种或支付对象不匹配")

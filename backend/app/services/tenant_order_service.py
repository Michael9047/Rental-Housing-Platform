"""按当前租客聚合不可变支付快照、订单状态及安全展示信息。"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract, ContractSignature
from app.models.payment import Payment, PaymentStatus
from app.models.property import Property
from app.models.property_image import PropertyImage
from app.models.user import User
from app.schemas.payment import PaymentEligibilityResponse, TenantOrderDetail, TenantOrderListItem
from app.services.order_state_policy import booking_is_confirmed, payment_status_can_pay, payment_status_value


STATUS_LABELS = {
    "payment_pending": "待支付",
    "payment_processing": "处理中",
    "payment_failed": "支付失败",
    "payment_expired": "支付超时",
    "cancelled": "已取消/已失效",
    "payment_review": "异常核对",
    "refund_pending": "退款处理中",
    "refunded": "已退款",
    "paid": "已支付",
}

FAILURE_REASONS = {
    "payment_failed": "支付未成功，可在支付期限内安全重试。",
    "payment_expired": "支付期限已过，预订未生效。",
    "cancelled": "订单已取消，预订未生效。",
    "payment_review": "付款信息正在人工核对，暂未确认预订成功。",
    "refund_pending": "异常付款正在安排退款。",
    "refunded": "款项已退款，预订未生效。",
}


class TenantOrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _mask_phone(value: str | None) -> str | None:
        if not value:
            return None
        compact = value.replace(" ", "")
        if compact.startswith("+86") and len(compact) >= 14:
            return f"+86 {compact[3:6]}****{compact[-4:]}"
        return f"{compact[:-8]}****{compact[-4:]}" if len(compact) >= 8 else "****"

    @staticmethod
    def _mask_email(value: str | None) -> str | None:
        if not value or "@" not in value:
            return None
        local, domain = value.split("@", 1)
        return f"{local[:1]}***@{domain}"

    @staticmethod
    def _payment_status(payment: Payment | None, booking: Booking) -> str:
        return payment_status_value(payment.status if payment else None, booking.status)

    @staticmethod
    def _amounts_verified(payment: Payment) -> bool:
        total = (payment.snapshot or {}).get("fees", {}).get("current_total", {})
        return (
            total.get("currency") == payment.settlement_currency
            and total.get("minor_units") == payment.settlement_amount_minor
        )

    @staticmethod
    def _pricing(booking: Booking) -> tuple[dict, dict]:
        pricing = (booking.application_data or {}).get("pricing_snapshot") or {}
        option = next((row for row in pricing.get("options", []) if row.get("months") == booking.lease_months), {})
        return pricing, option

    async def _latest_payment(self, booking_id: int) -> Payment | None:
        return await self.session.scalar(
            select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc())
        )

    async def payment_eligibility(self, booking_id: int, tenant_id: int) -> PaymentEligibilityResponse:
        booking = await self.session.scalar(
            select(Booking).where(Booking.id == booking_id, Booking.tenant_id == tenant_id)
        )
        if not booking:
            raise LookupError("订单不存在或无权查看")
        payment = await self._latest_payment(booking.id)
        payment_status = self._payment_status(payment, booking)
        now = datetime.now(timezone.utc)
        expires_at = payment.expires_at if payment else booking.payment_expires_at
        if not expires_at:
            raise LookupError("订单缺少支付截止时间")
        reason = None
        contract = await self.session.scalar(
            select(Contract).where(Contract.booking_id == booking.id, Contract.status == "signed")
            .order_by(Contract.version.desc())
        )
        signature = None
        if contract:
            signature = await self.session.scalar(
                select(ContractSignature).where(
                    ContractSignature.agreement_id == contract.id,
                    ContractSignature.tenant_user_id == tenant_id,
                )
            )
        processing = await self.session.scalar(
            select(Payment.id).where(
                Payment.booking_id == booking.id,
                Payment.status == PaymentStatus.processing,
            ).limit(1)
        )
        if booking.status == BookingStatus.payment_processing or processing:
            reason = "支付结果确认中，请勿重复支付"
        elif expires_at <= now or booking.status == BookingStatus.payment_expired:
            reason = "支付期限已过，请重新预订"
        elif booking.status not in {BookingStatus.payment_pending, BookingStatus.payment_failed}:
            reason = "当前订单状态不允许支付"
        elif not booking.inventory_reserved:
            reason = "房源预留已失效，请重新预订"
        elif not contract or not signature:
            reason = "未找到当前版本的有效已签合同"
        elif payment and not self._amounts_verified(payment):
            reason = "订单金额或币种已变化，请联系客服"
        can_pay = reason is None and payment_status_can_pay(payment_status)
        return PaymentEligibilityResponse(
            booking_id=booking.id,
            can_pay=can_pay,
            order_status=booking.status.value,
            payment_status=payment_status,
            expires_at=expires_at,
            reason=reason,
            payment_id=payment.id if payment else None,
        )

    async def _item(self, booking: Booking, payment: Payment | None, contract: Contract, property_obj: Property, image: PropertyImage | None) -> TenantOrderListItem:
        pricing, option = self._pricing(booking)
        snapshot = payment.snapshot if payment else {}
        fees = (snapshot or {}).get("fees") or option.get("prices", {})
        local_total = fees.get("current_total") or fees.get("amount_due_now", {}).get("local", {})
        cny_total = option.get("prices", {}).get("amount_due_now", {}).get("cny", {})
        payment_status = self._payment_status(payment, booking)
        amounts_verified = self._amounts_verified(payment) if payment else bool(local_total)
        webhook_confirmed = bool(payment and payment.status == PaymentStatus.success and payment.paid_at and payment.transaction_id)
        confirmed = booking_is_confirmed(booking.status, payment_status, amounts_verified=amounts_verified, webhook_confirmed=webhook_confirmed)
        eligibility = await self.payment_eligibility(booking.id, booking.tenant_id)
        expires_at = payment.expires_at if payment else booking.payment_expires_at
        remaining = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
        settlement_currency = payment.settlement_currency if payment else local_total.get("currency", pricing.get("local_currency", "CNY"))
        settlement_amount = payment.settlement_amount_minor if payment else int(local_total.get("minor_units", 0))
        return TenantOrderListItem(
            booking_id=booking.id,
            order_id=payment.order_id if payment else f"BOOKING-{booking.id}",
            agreement_id=contract.id,
            agreement_number=contract.agreement_number or contract.id,
            property_id=property_obj.id,
            property_name=property_obj.title,
            property_image_url=f"/api/v1/uploads/{image.filename}" if image else None,
            property_city=property_obj.district,
            property_address=property_obj.address,
            lease_start_date=(snapshot or {}).get("commencement_date") or booking.scheduled_date,
            lease_end_date=(snapshot or {}).get("expiry_date") or option.get("end_date"),
            lease_months=booking.lease_months,
            settlement_currency=settlement_currency,
            settlement_amount_minor=settlement_amount,
            cny_reference_amount_minor=payment.cny_reference_amount_minor if payment else int(cny_total.get("minor_units", settlement_amount)),
            property_currency=payment.property_currency if payment else pricing.get("local_currency", settlement_currency),
            property_amount_minor=int(local_total.get("minor_units", settlement_amount)),
            order_status=booking.status.value,
            payment_status=payment_status,
            booking_status="confirmed" if confirmed else "not_confirmed",
            status_label=STATUS_LABELS.get(payment_status, payment_status),
            created_at=booking.created_at,
            expires_at=expires_at,
            remaining_payment_seconds=remaining,
            can_pay=eligibility.can_pay,
            payment_action_label="重新支付" if eligibility.can_pay and payment_status == "payment_failed" else "立即支付" if eligibility.can_pay else None,
            failure_reason=FAILURE_REASONS.get(payment_status),
        )

    async def list_for_tenant(self, tenant_id: int) -> list[TenantOrderListItem]:
        bookings = list(await self.session.scalars(
            select(Booking).where(Booking.tenant_id == tenant_id).order_by(Booking.created_at.desc())
        ))
        result = []
        for booking in bookings:
            payment = await self._latest_payment(booking.id)
            contract = await self.session.scalar(
                select(Contract).where(Contract.booking_id == booking.id, Contract.status == "signed")
                .order_by(Contract.version.desc())
            )
            property_obj = await self.session.get(Property, booking.property_id)
            if not contract or not property_obj:
                continue
            image = await self.session.scalar(
                select(PropertyImage).where(PropertyImage.property_id == property_obj.id)
                .order_by(PropertyImage.is_primary.desc(), PropertyImage.sort_order, PropertyImage.id)
            )
            result.append(await self._item(booking, payment, contract, property_obj, image))
        return result

    async def detail_for_tenant(self, booking_id: int, tenant_id: int) -> TenantOrderDetail:
        booking = await self.session.scalar(
            select(Booking).where(Booking.id == booking_id, Booking.tenant_id == tenant_id)
        )
        if not booking:
            raise LookupError("订单不存在或无权查看")
        payment = await self._latest_payment(booking.id)
        contract = await self.session.scalar(
            select(Contract).where(Contract.booking_id == booking.id, Contract.status == "signed")
            .order_by(Contract.version.desc())
        )
        property_obj = await self.session.get(Property, booking.property_id)
        tenant = await self.session.get(User, tenant_id)
        if not contract or not property_obj or not tenant:
            raise LookupError("订单关联数据不完整")
        image = await self.session.scalar(
            select(PropertyImage).where(PropertyImage.property_id == property_obj.id)
            .order_by(PropertyImage.is_primary.desc(), PropertyImage.sort_order, PropertyImage.id)
        )
        item = await self._item(booking, payment, contract, property_obj, image)
        pricing, option = self._pricing(booking)
        fees = (payment.snapshot or {}).get("fees", {}) if payment else option.get("prices", {})
        deposit = fees.get("deposit", {})
        service_fee = fees.get("service_fee", {})
        tax = fees.get("tax", {})
        return TenantOrderDetail(
            **item.model_dump(),
            applicant_name=(payment.snapshot or {}).get("tenant_name") or tenant.username,
            applicant_phone_masked=self._mask_phone(tenant.phone),
            applicant_email_masked=self._mask_email(tenant.email),
            property_type=property_obj.property_type.value,
            property_country=property_obj.country.value,
            property_description=property_obj.description,
            monthly_rent_minor=int(property_obj.price_monthly * 100),
            deposit_amount_minor=int((deposit.get("local") or deposit).get("minor_units", 0)),
            service_fee_amount_minor=int((service_fee.get("local") or service_fee).get("minor_units", 0)),
            tax_amount_minor=int((tax.get("local") or tax).get("minor_units", 0)),
            exchange_rate=payment.exchange_rate if payment else pricing.get("exchange_rate_to_cny", 1),
            exchange_rate_source=payment.exchange_rate_source if payment else pricing.get("exchange_rate_source", "订单价格快照"),
            exchange_rate_timestamp=payment.exchange_rate_timestamp if payment else datetime.fromisoformat(str(pricing.get("exchange_rate_at")).replace("Z", "+00:00")),
            status_updated_at=booking.updated_at,
            paid_at=payment.paid_at if payment else None,
            transaction_id_masked=(f"{payment.transaction_id[:4]}****{payment.transaction_id[-4:]}" if payment and payment.transaction_id and len(payment.transaction_id) > 8 else "****" if payment and payment.transaction_id else None),
            webhook_confirmed=bool(payment and payment.status == PaymentStatus.success and payment.paid_at and payment.transaction_id),
            amounts_verified=self._amounts_verified(payment) if payment else bool(option),
            inventory_reserved=booking.inventory_reserved,
        )

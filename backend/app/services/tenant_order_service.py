"""Tenant-facing order projection built from bookings, contracts and payments."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract
from app.models.payment import Payment
from app.models.unit_type import UnitType, UnitTypeImage
from app.models.institute import Institute
from app.schemas.payment import PaymentEligibilityResponse, TenantOrderDetail, TenantOrderListItem


PAYABLE_STATUSES = {
    BookingStatus.contract_signed,
    BookingStatus.payment_pending,
    BookingStatus.payment_failed,
}


class TenantOrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _latest_contract(self, booking_id: int) -> Contract | None:
        return await self.session.scalar(
            select(Contract)
            .where(Contract.booking_id == booking_id)
            .order_by(Contract.version.desc())
        )

    async def _latest_payment(self, booking_id: int) -> Payment | None:
        return await self.session.scalar(
            select(Payment)
            .where(Payment.booking_id == booking_id)
            .order_by(Payment.created_at.desc())
        )

    async def _unit_context(self, unit_type_id: int | None) -> tuple[UnitType | None, Institute | None, str | None]:
        unit = await self.session.get(UnitType, unit_type_id) if unit_type_id else None
        institute = await self.session.get(Institute, unit.institute_id) if unit else None
        image = None
        if unit:
            image_row = await self.session.scalar(
                select(UnitTypeImage)
                .where(UnitTypeImage.unit_type_id == unit.id)
                .order_by(UnitTypeImage.is_primary.desc(), UnitTypeImage.sort_order, UnitTypeImage.id)
            )
            image = f"/api/v1/uploads/{image_row.filename}" if image_row else None
        return unit, institute, image

    def _remaining_seconds(self, expires_at: datetime) -> int:
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return max(0, int((expires_at - now).total_seconds()))

    async def _build_item(self, booking: Booking) -> TenantOrderListItem:
        contract = await self._latest_contract(booking.id)
        payment = await self._latest_payment(booking.id)
        unit, institute, image = await self._unit_context(booking.unit_type_id or booking.property_id)
        expires_at = (
            payment.expires_at if payment else
            booking.payment_expires_at if booking.payment_expires_at else
            datetime.now(timezone.utc) + timedelta(hours=24)
        )
        payment_status = payment.status.value if payment and hasattr(payment.status, "value") else (str(payment.status) if payment else booking.deposit_status or "unpaid")
        booking_status = booking.status.value if hasattr(booking.status, "value") else str(booking.status)
        amount = int((payment.settlement_amount_minor if payment else None) or (booking.deposit_amount or 0) + (booking.service_fee or 0))
        currency = (payment.settlement_currency if payment else None) or (unit.currency if unit else None) or "CNY"
        can_pay = booking.status in PAYABLE_STATUSES and contract is not None and contract.status == "signed"
        return TenantOrderListItem(
            booking_id=booking.id,
            order_id=payment.order_id if payment else f"BOOKING-{booking.id}",
            agreement_id=contract.id if contract else "",
            agreement_number=contract.agreement_number if contract and contract.agreement_number else "",
            property_id=unit.id if unit else booking.property_id,
            property_name=unit.name if unit else f"房源 #{booking.property_id}",
            property_image_url=image,
            property_city=institute.city if institute and institute.city else "",
            property_address=institute.address if institute and institute.address else "",
            lease_start_date=booking.contract_start.isoformat() if booking.contract_start else booking.scheduled_date,
            lease_end_date=booking.contract_end.isoformat() if booking.contract_end else None,
            lease_months=booking.lease_months,
            settlement_currency=currency,
            settlement_amount_minor=amount,
            cny_reference_amount_minor=int((payment.cny_reference_amount_minor if payment else None) or amount),
            property_currency=currency,
            property_amount_minor=amount,
            order_status=booking_status,
            payment_status=payment_status,
            booking_status=booking_status,
            status_label=booking_status,
            created_at=booking.created_at,
            expires_at=expires_at,
            remaining_payment_seconds=self._remaining_seconds(expires_at),
            can_pay=can_pay,
            payment_action_label="去支付" if can_pay else None,
            failure_reason=None,
        )

    async def list_for_tenant(self, tenant_id: int) -> list[TenantOrderListItem]:
        rows = await self.session.scalars(
            select(Booking)
            .where(Booking.user_id == tenant_id)
            .order_by(Booking.created_at.desc())
        )
        return [await self._build_item(row) for row in rows]

    async def detail_for_tenant(self, booking_id: int, tenant_id: int) -> TenantOrderDetail:
        booking = await self.session.get(Booking, booking_id)
        if not booking or booking.user_id != tenant_id:
            raise LookupError("订单不存在或无权查看")
        item = await self._build_item(booking)
        unit, institute, _ = await self._unit_context(booking.unit_type_id or booking.property_id)
        payment = await self._latest_payment(booking.id)
        applicant = (booking.application_data or {}).get("applicant") or {}
        amount = item.settlement_amount_minor
        return TenantOrderDetail(
            **item.model_dump(),
            applicant_name=applicant.get("name") or f"租客 #{booking.user_id}",
            applicant_phone_masked=None,
            applicant_email_masked=None,
            property_type=str(unit.property_type or "") if unit else "",
            property_country=institute.country if institute and institute.country else "",
            property_description=unit.description if unit else None,
            monthly_rent_minor=int(unit.base_rent or 0) if unit else 0,
            deposit_amount_minor=int(booking.deposit_amount or 0),
            service_fee_amount_minor=int(booking.service_fee or 0),
            tax_amount_minor=0,
            exchange_rate=Decimal(str(payment.exchange_rate if payment else 1)),
            exchange_rate_source=payment.exchange_rate_source if payment else "local unit type snapshot",
            exchange_rate_timestamp=payment.exchange_rate_timestamp if payment else item.created_at,
            status_updated_at=booking.updated_at,
            paid_at=payment.paid_at if payment else None,
            transaction_id_masked=None,
            webhook_confirmed=bool(payment and payment.status.value == "success"),
            amounts_verified=bool(payment),
            inventory_reserved=bool(booking.inventory_reserved),
        )

    async def payment_eligibility(self, booking_id: int, tenant_id: int) -> PaymentEligibilityResponse:
        booking = await self.session.get(Booking, booking_id)
        if not booking or booking.user_id != tenant_id:
            raise LookupError("订单不存在或无权查看")
        payment = await self._latest_payment(booking_id)
        contract = await self._latest_contract(booking_id)
        expires_at = (
            payment.expires_at if payment else
            booking.payment_expires_at if booking.payment_expires_at else
            datetime.now(timezone.utc) + timedelta(hours=24)
        )
        payment_status = payment.status.value if payment and hasattr(payment.status, "value") else (booking.deposit_status or "unpaid")
        can_pay = booking.status in PAYABLE_STATUSES and contract is not None and contract.status == "signed"
        reason = None if can_pay else "请先完成合同签署" if contract and contract.status != "signed" else "订单当前状态不可支付"
        return PaymentEligibilityResponse(
            booking_id=booking_id,
            can_pay=can_pay,
            order_status=booking.status.value if hasattr(booking.status, "value") else str(booking.status),
            payment_status=payment_status,
            expires_at=expires_at,
            reason=reason,
            payment_id=payment.id if payment else None,
        )

    async def list_by_tenant(self, tenant_id: int):
        return await self.list_for_tenant(tenant_id)

    async def list_all(self):
        rows = await self.session.scalars(select(Booking).order_by(Booking.created_at.desc()))
        return [await self._build_item(row) for row in rows]

    async def get(self, order_id: int):
        return await self._build_item(await self.session.get(Booking, order_id))

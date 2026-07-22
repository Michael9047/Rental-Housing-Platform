"""按当前租客聚合不可变合同、支付、预订和房源信息并计算合同分类。"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract, ContractSignature
from app.models.payment import Payment, PaymentStatus
from app.models.property import Property
from app.models.property_image import PropertyImage
from app.schemas.contract import TenantContractDetail, TenantContractListItem
from app.services.booking_availability_service import BookingAvailabilityService
from app.services.order_state_policy import booking_is_confirmed, classify_contract, payment_status_can_pay, payment_status_value


class TenantContractService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _now(timezone_name: str) -> datetime:
        return datetime.now(ZoneInfo(timezone_name))

    @staticmethod
    def _date(value) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    @staticmethod
    def _payment_status(payment: Payment | None, booking: Booking) -> str:
        return payment_status_value(payment.status if payment else None, booking.status)

    @staticmethod
    def _labels(payment_status: str, reservation_status: str, *, waiting: bool, category: str) -> list[str]:
        payment_labels = {
            "payment_pending": "等待支付", "unpaid": "等待支付",
            "payment_processing": "支付处理中", "payment_failed": "支付失败，可重试",
            "payment_expired": "支付超时", "paid": "已支付", "refunded": "已失效",
            "refund_pending": "预订未成功", "payment_review": "预订未成功", "cancelled": "已失效",
        }
        labels = [payment_labels.get(payment_status, payment_status)]
        labels.append("预订成功" if reservation_status == "confirmed" else "预订未成功")
        if waiting and reservation_status == "confirmed": labels.append("等待入住")
        elif reservation_status == "confirmed" and category in {"effective", "expiring_soon"}: labels.append("租住中")
        if category == "expiring_soon": labels.append("临期失效")
        if category == "invalid": labels.append("已失效")
        return list(dict.fromkeys(labels))

    async def _item(self, contract: Contract, signature: ContractSignature) -> TenantContractListItem:
        booking = await self.session.get(Booking, contract.booking_id)
        property_obj = await self.session.get(Property, contract.property_id)
        payment = await self.session.scalar(select(Payment).where(Payment.booking_id == contract.booking_id).order_by(Payment.created_at.desc()))
        image = await self.session.scalar(select(PropertyImage).where(PropertyImage.property_id == contract.property_id).order_by(PropertyImage.is_primary.desc(), PropertyImage.sort_order, PropertyImage.id))
        if not booking or not property_obj:
            raise LookupError("合同关联订单或房源不存在")

        snapshot = contract.snapshot or {}
        payment_snapshot = payment.snapshot if payment else {}
        pricing = (booking.application_data or {}).get("pricing_snapshot") or {}
        option = next((row for row in pricing.get("options", []) if row.get("months") == booking.lease_months), {})
        lease_start = self._date(payment_snapshot.get("commencement_date") or snapshot.get("commencement_date") or booking.scheduled_date)
        lease_end = self._date(payment_snapshot.get("expiry_date") or snapshot.get("expiry_date") or option.get("end_date"))
        property_timezone = signature.property_timezone or BookingAvailabilityService.timezone_for_country(property_obj.country)
        now = self._now(property_timezone)
        today = now.date()
        payment_status = self._payment_status(payment, booking)
        payment_total = ((payment.snapshot or {}).get("fees", {}).get("current_total", {}) if payment else {})
        amounts_verified = bool(payment and payment_total.get("currency") == payment.settlement_currency and payment_total.get("minor_units") == payment.settlement_amount_minor)
        webhook_confirmed = bool(payment and payment.paid_at and payment.transaction_id)
        reservation_status = "confirmed" if booking_is_confirmed(
            booking.status, payment_status,
            amounts_verified=amounts_verified,
            webhook_confirmed=webhook_confirmed,
        ) else "not_confirmed"
        agreement_status = "terminated" if contract.status == "terminated" else "signed"
        threshold = get_settings().contract_expiring_soon_days
        classification = classify_contract(
            agreement_status=agreement_status, booking_status=booking.status,
            payment_status=payment_status, today=today, lease_end=lease_end,
            expiring_days=threshold,
        )
        category, invalid_reason = classification.category, classification.invalid_reason

        payment_deadline = payment.expires_at if payment else booking.payment_expires_at
        remaining_payment_seconds = None
        if payment_deadline and payment_status in {"payment_pending", "payment_failed", "unpaid"}:
            remaining_payment_seconds = max(0, int((payment_deadline - datetime.now(timezone.utc)).total_seconds()))
        can_pay = category == "pending_effective" and payment_status_can_pay(payment_status) and bool(remaining_payment_seconds)
        remaining_contract_days = classification.remaining_days if category in {"effective", "expiring_soon"} else None
        waiting = bool(lease_start and today < lease_start and reservation_status == "confirmed")
        category_label = {"pending_effective":"待生效","effective":"已生效","expiring_soon":"临期失效","invalid":"已失效"}[category]

        return TenantContractListItem(
            agreement_id=contract.id, agreement_number=contract.agreement_number or contract.id,
            agreement_version=contract.version, agreement_content_hash=contract.content_hash or "",
            order_id=payment.order_id if payment else f"BOOKING-{booking.id}", booking_id=booking.id,
            property_id=property_obj.id, tenant_user_id=contract.tenant_id, signed_at=signature.signed_at,
            lease_start_date=lease_start.isoformat() if lease_start else None,
            lease_end_date=lease_end.isoformat() if lease_end else None, lease_months=booking.lease_months,
            property_timezone=property_timezone, property_name=property_obj.title, property_address=property_obj.address,
            property_image_url=f"/api/v1/uploads/{image.filename}" if image else None,
            payment_status=payment_status, booking_status=reservation_status,
            reservation_status=reservation_status, agreement_status=agreement_status,
            category=category, category_label=category_label,
            status_labels=self._labels(payment_status,reservation_status,waiting=waiting,category=category),
            invalid_reason=invalid_reason,
            settlement_currency=payment.settlement_currency if payment else None,
            settlement_amount_minor=payment.settlement_amount_minor if payment else None,
            payment_expires_at=payment_deadline, remaining_payment_seconds=remaining_payment_seconds,
            remaining_contract_days=remaining_contract_days, can_pay=can_pay, waiting_for_move_in=waiting,
            signed_pdf_available=bool(signature.signed_pdf_object_key or contract.file_path),
        )

    async def list_for_tenant(self, tenant_user_id: int) -> list[TenantContractListItem]:
        rows = await self.session.execute(
            select(Contract, ContractSignature)
            .join(ContractSignature, ContractSignature.agreement_id == Contract.id)
            .where(Contract.tenant_id == tenant_user_id, Contract.status.in_(["signed", "terminated"]))
            .order_by(ContractSignature.signed_at.desc())
        )
        return [await self._item(contract, signature) for contract, signature in rows.all()]

    async def detail_for_tenant(self, agreement_id: str, tenant_user_id: int) -> TenantContractDetail:
        row = await self.session.execute(
            select(Contract, ContractSignature)
            .join(ContractSignature, ContractSignature.agreement_id == Contract.id)
            .where(Contract.id == agreement_id, Contract.tenant_id == tenant_user_id)
        )
        pair = row.first()
        if not pair:
            raise LookupError("合同不存在或无权查看")
        contract, signature = pair
        item = await self._item(contract, signature)
        return TenantContractDetail(**item.model_dump(), content=contract.content, snapshot=contract.snapshot or {}, signature_url=f"/api/v1/contracts/my/{contract.id}/signature")

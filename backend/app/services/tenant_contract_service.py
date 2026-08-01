"""租客端合同列表与详情查询服务。"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract, ContractSignature
from app.models.payment import Payment, PaymentStatus
from app.models.property import Room
from app.models.unit_type import UnitType
from app.models.property_image import RoomImage
from app.schemas.contract import TenantContractDetail, TenantContractListItem
from app.services.order_state_policy import booking_is_confirmed, payment_status_can_pay, payment_status_value
from app.services.lease_pricing_service import LeasePricingService


STATUS_LABELS = {
    "generated": "待签署",
    "signed": "已签署",
    "expired": "已过期",
    "voided": "已作废",
}

CATEGORY_LABELS = {
    "pending_effective": "待生效",
    "effective": "已生效",
    "expiring_soon": "即将到期",
    "invalid": "已失效",
}


class TenantContractService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _category(self, booking: Booking, contract: Contract) -> str:
        if contract.status != "signed":
            if booking.status in (BookingStatus.cancelled, BookingStatus.payment_expired):
                return "invalid"
            return "pending_effective"
        if not booking.scheduled_date:
            return "pending_effective"
        try:
            move_in = datetime.fromisoformat(booking.scheduled_date).date()
            today = datetime.now(timezone.utc).date()
            days = (move_in - today).days
            if days <= 30:
                return "expiring_soon" if days > 0 else "effective"
            return "pending_effective"
        except (ValueError, TypeError):
            return "pending_effective"

    async def _latest_payment(self, booking_id: int) -> Payment | None:
        return await self.session.scalar(
            select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc())
        )

    async def _build_item(self, booking, contract, payment, room, image):
        ut = getattr(room, 'unit_type', None)
        inst = getattr(ut, 'institute', None) if ut else None
        payment_status = payment_status_value(
            payment.status if payment else None, booking.status
        )
        category = self._category(booking, contract)
        expires_at = payment.expires_at if payment else booking.payment_expires_at
        remaining_seconds = 0
        if expires_at:
            remaining_seconds = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
        remaining_contract_days = None
        if booking.scheduled_date and contract.status == "signed":
            try:
                move_in = datetime.fromisoformat(booking.scheduled_date).date()
                remaining_contract_days = (move_in - datetime.now(timezone.utc).date()).days
            except (ValueError, TypeError):
                pass
        confirmed = booking_is_confirmed(
            booking.status, payment_status,
            amounts_verified=bool(payment and payment.status == PaymentStatus.success),
            webhook_confirmed=bool(payment and payment.status == PaymentStatus.success and payment.paid_at),
        )
        return TenantContractListItem(
            agreement_id=contract.id,
            agreement_number=contract.agreement_number or contract.id,
            agreement_version=contract.version,
            agreement_content_hash=contract.content_hash or "",
            order_id=payment.order_id if payment else f"BOOKING-{booking.id}",
            booking_id=booking.id,
            property_id=room.id,
            tenant_user_id=booking.tenant_id,
            signed_at=contract.signed_at,
            lease_start_date=booking.scheduled_date,
            lease_end_date=LeasePricingService.add_calendar_months(datetime.fromisoformat(booking.scheduled_date).date(), booking.lease_months).isoformat() if booking.scheduled_date and booking.lease_months else None,
            lease_months=booking.lease_months,
            property_timezone="Asia/Shanghai",
            property_name=getattr(ut, 'name', None) or room.room_number or f"Room #{room.id}",
            property_address=getattr(inst, 'address', None) or "",
            property_image_url=f"/api/v1/uploads/{image.filename}" if image else None,
            payment_status=payment_status,
            booking_status="confirmed" if confirmed else "not_confirmed",
            reservation_status=booking.status.value,
            agreement_status=contract.status,
            category=category,
            category_label=CATEGORY_LABELS.get(category, category),
            status_labels=[STATUS_LABELS.get(contract.status, contract.status)],
            invalid_reason=None if category != "invalid" else "订单已取消或支付超时",
            settlement_currency=payment.settlement_currency if payment else "CNY",
            settlement_amount_minor=payment.settlement_amount_minor if payment else 0,
            payment_expires_at=expires_at,
            remaining_payment_seconds=remaining_seconds,
            remaining_contract_days=remaining_contract_days,
            can_pay=payment_status_can_pay(payment_status),
            waiting_for_move_in=category == "pending_effective" and contract.status == "signed",
            signed_pdf_available=contract.status == "signed" and contract.file_path is not None,
        )

    async def list_for_tenant(self, user_id: int):
        bookings = list(await self.session.scalars(
            select(Booking).where(Booking.tenant_id == user_id).order_by(Booking.created_at.desc())
        ))
        result = []
        for booking in bookings:
            contract = await self.session.scalar(
                select(Contract).where(Contract.booking_id == booking.id).order_by(Contract.version.desc())
            )
            if not contract:
                continue
            room = (await self.session.scalars(
                select(Room).where(Room.id == booking.property_id).options(selectinload(Room.unit_type).selectinload(UnitType.institute))
            )).unique().first()
            if not room:
                continue
            payment = await self._latest_payment(booking.id)
            image = await self.session.scalar(
                select(RoomImage).where(RoomImage.room_id == room.id)
                .order_by(RoomImage.is_primary.desc(), RoomImage.sort_order, RoomImage.id)
            )
            item = await self._build_item(booking, contract, payment, room, image)
            if item:
                result.append(item)
        return result

    async def detail_for_tenant(self, agreement_id: str, user_id: int):
        contract = await self.session.scalar(
            select(Contract).where(Contract.id == agreement_id, Contract.tenant_id == user_id)
        )
        if not contract:
            raise LookupError("合同不存在或无权查看")
        booking = await self.session.get(Booking, contract.booking_id)
        if not booking:
            raise LookupError("订单不存在")
        room = await self.session.get(Room, booking.property_id)
        if not room:
            raise LookupError("房源不存在")
        payment = await self._latest_payment(booking.id)
        image = await self.session.scalar(
            select(RoomImage).where(RoomImage.room_id == room.id)
            .order_by(RoomImage.is_primary.desc(), RoomImage.sort_order, RoomImage.id)
        )
        item = await self._build_item(booking, contract, payment, room, image)
        if not item:
            raise LookupError("合同数据不完整")
        signature = await self.session.scalar(
            select(ContractSignature).where(
                ContractSignature.agreement_id == agreement_id,
                ContractSignature.tenant_user_id == user_id,
            )
        )
        return TenantContractDetail(
            content=contract.content,
            snapshot=contract.snapshot or {},
            signature_url=f"/api/v1/contracts/my/{agreement_id}/signature" if signature else "",
            **item.model_dump(),
        )

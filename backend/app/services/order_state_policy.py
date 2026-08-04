"""合同、订单和个人中心共用的服务端状态映射与分类策略。"""

from dataclasses import dataclass
from datetime import date

from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


PAYMENT_STATUS_MAP = {
    PaymentStatus.success: "paid",
    PaymentStatus.processing: "payment_processing",
    PaymentStatus.pending: "payment_pending",
    PaymentStatus.failed: "payment_failed",
    PaymentStatus.expired: "payment_expired",
    PaymentStatus.review: "payment_review",
    PaymentStatus.refund_pending: "refund_pending",
    PaymentStatus.refunded: "refunded",
    PaymentStatus.closed: "cancelled",
}


def payment_status_value(payment_status: PaymentStatus | None, booking_status: BookingStatus) -> str:
    if payment_status is not None:
        if booking_status == BookingStatus.cancelled:
            return "cancelled"
        return PAYMENT_STATUS_MAP[payment_status]
    return booking_status.value if booking_status in {
        BookingStatus.payment_pending, BookingStatus.payment_processing,
        BookingStatus.payment_failed, BookingStatus.payment_expired,
        BookingStatus.refund_pending, BookingStatus.refunded,
        BookingStatus.payment_review, BookingStatus.cancelled,
    } else "unpaid"


def booking_is_confirmed(booking_status: BookingStatus, payment_status: str, *, amounts_verified: bool = True, webhook_confirmed: bool = True) -> bool:
    return booking_status == BookingStatus.paid and payment_status == "paid" and amounts_verified and webhook_confirmed


def payment_status_can_pay(payment_status: str) -> bool:
    return payment_status in {"payment_pending", "payment_failed"}


@dataclass(frozen=True)
class ContractClassification:
    category: str
    invalid_reason: str | None = None
    remaining_days: int | None = None


def classify_contract(
    *, agreement_status: str, booking_status: BookingStatus, payment_status: str,
    today: date, lease_end: date | None, expiring_days: int,
) -> ContractClassification:
    if agreement_status == "terminated":
        return ContractClassification("invalid", "合同已正式终止")
    if booking_status == BookingStatus.payment_expired or payment_status == "payment_expired":
        return ContractClassification("invalid", "支付期限已过，预订未生效")
    if booking_status == BookingStatus.cancelled or payment_status == "cancelled":
        return ContractClassification("invalid", "订单已取消，合同未生效")
    if booking_status == BookingStatus.refunded or payment_status == "refunded":
        return ContractClassification("invalid", "订单已退款，合同已失效")
    if booking_status in {BookingStatus.payment_review, BookingStatus.refund_pending} or payment_status in {"payment_review", "refund_pending"}:
        return ContractClassification("invalid", "预订未生效，付款正在核对或退款")
    if lease_end and today > lease_end:
        return ContractClassification("invalid", "租赁期限已经结束", 0)
    if booking_is_confirmed(booking_status, payment_status):
        remaining = (lease_end - today).days if lease_end else None
        category = "expiring_soon" if remaining is not None and remaining <= expiring_days else "effective"
        return ContractClassification(category, remaining_days=remaining)
    return ContractClassification("pending_effective")

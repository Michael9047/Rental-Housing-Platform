"""订单状态判定策略 — 供 tenant_order_service / payment_service 共享。"""
from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


def payment_status_value(
    payment_status: PaymentStatus | None, booking_status: BookingStatus
) -> str:
    """将支付状态 + 订单状态映射为面向租客的统一展示值。"""
    if payment_status is None:
        if booking_status == BookingStatus.payment_expired:
            return "payment_expired"
        if booking_status == BookingStatus.cancelled:
            return "cancelled"
        if booking_status == BookingStatus.refunded:
            return "refunded"
        if booking_status == BookingStatus.refund_pending:
            return "refund_pending"
        if booking_status in (BookingStatus.payment_pending, BookingStatus.payment_processing):
            return "payment_pending"
        if booking_status == BookingStatus.payment_failed:
            return "payment_failed"
        return "payment_pending"
    return payment_status.value


def payment_status_can_pay(payment_status: str) -> bool:
    """当前支付状态是否允许重新发起支付。"""
    return payment_status in ("payment_pending", "payment_failed")


def booking_is_confirmed(
    booking_status: BookingStatus,
    payment_status: str,
    *,
    amounts_verified: bool = True,
    webhook_confirmed: bool = False,
) -> bool:
    """订单是否已确认支付（租客侧展示为「已预订」）。"""
    if booking_status in (BookingStatus.paid, BookingStatus.completed):
        return True
    if booking_status == BookingStatus.payment_review and webhook_confirmed and amounts_verified:
        return True
    return False

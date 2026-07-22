"""个人中心合同与订单在完整生命周期中的状态一致性测试。"""

from datetime import date, timedelta

from app.models.booking import BookingStatus
from app.services.order_state_policy import booking_is_confirmed, classify_contract, payment_status_can_pay


TODAY = date(2026, 7, 22)


def test_signed_to_paid_to_expiring_to_ended_flow_is_consistent():
    pending = classify_contract(
        agreement_status="signed", booking_status=BookingStatus.payment_pending,
        payment_status="payment_pending", today=TODAY,
        lease_end=TODAY + timedelta(days=365), expiring_days=30,
    )
    assert pending.category == "pending_effective"
    assert payment_status_can_pay("payment_pending") is True
    assert booking_is_confirmed(BookingStatus.payment_pending, "payment_pending") is False

    effective = classify_contract(
        agreement_status="signed", booking_status=BookingStatus.paid,
        payment_status="paid", today=TODAY,
        lease_end=TODAY + timedelta(days=31), expiring_days=30,
    )
    assert effective.category == "effective"
    assert booking_is_confirmed(BookingStatus.paid, "paid") is True
    assert payment_status_can_pay("paid") is False

    expiring = classify_contract(
        agreement_status="signed", booking_status=BookingStatus.paid,
        payment_status="paid", today=TODAY,
        lease_end=TODAY + timedelta(days=30), expiring_days=30,
    )
    assert expiring.category == "expiring_soon"
    assert booking_is_confirmed(BookingStatus.paid, "paid") is True

    ended = classify_contract(
        agreement_status="signed", booking_status=BookingStatus.paid,
        payment_status="paid", today=TODAY,
        lease_end=TODAY - timedelta(days=1), expiring_days=30,
    )
    assert ended.category == "invalid" and ended.invalid_reason == "租赁期限已经结束"
    assert booking_is_confirmed(BookingStatus.paid, "paid") is True


def test_payment_expiry_removes_payability_and_invalidates_contract():
    expired = classify_contract(
        agreement_status="signed", booking_status=BookingStatus.payment_expired,
        payment_status="payment_expired", today=TODAY,
        lease_end=TODAY + timedelta(days=365), expiring_days=30,
    )
    assert payment_status_can_pay("payment_expired") is False
    assert expired.category == "invalid"
    assert expired.invalid_reason == "支付期限已过，预订未生效"


def test_processing_and_cancelled_never_count_as_payable():
    assert payment_status_can_pay("payment_processing") is False
    assert payment_status_can_pay("cancelled") is False
    assert payment_status_can_pay("payment_failed") is True

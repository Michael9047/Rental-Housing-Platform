"""管理员订单归档的最终状态与金额展示规则测试。"""
from types import SimpleNamespace

from app.api.v1.routes.admin_orders import (
    FINAL_CANCELLED,
    FINAL_SUCCESS,
    _base_statement,
    _category,
    _latest_payments,
    _payment_amount_minor,
)
from app.models.booking import BookingStatus
from app.models.user import UserRole


def test_only_real_final_statuses_are_archived() -> None:
    assert FINAL_SUCCESS == {BookingStatus.completed}
    assert FINAL_CANCELLED == {
        BookingStatus.cancelled,
        BookingStatus.rejected,
        BookingStatus.payment_expired,
    }
    assert BookingStatus.paid not in FINAL_SUCCESS | FINAL_CANCELLED
    assert BookingStatus.contract_signed not in FINAL_SUCCESS | FINAL_CANCELLED
    assert BookingStatus.payment_pending not in FINAL_SUCCESS | FINAL_CANCELLED


def test_final_status_categories_use_frontend_values() -> None:
    assert _category(BookingStatus.completed) == "completed"
    assert _category(BookingStatus.cancelled) == "cancelled"
    assert _category(BookingStatus.rejected) == "cancelled"


def test_actual_payment_amount_is_not_replaced_by_booking_deposit() -> None:
    booking = SimpleNamespace(deposit_amount=2000)
    payment = SimpleNamespace(settlement_amount_minor=188800, amount=1888)
    assert _payment_amount_minor(payment, booking) == 188800


def test_legacy_payment_uses_its_own_amount_when_minor_units_missing() -> None:
    booking = SimpleNamespace(deposit_amount=2000)
    payment = SimpleNamespace(settlement_amount_minor=0, amount=1350)
    assert _payment_amount_minor(payment, booking) == 135000


def test_latest_payment_per_booking_is_retained() -> None:
    newest = SimpleNamespace(booking_id=1)
    older = SimpleNamespace(booking_id=1)
    assert _latest_payments([newest, older])[1] is newest


def test_bm_query_is_constrained_to_its_assigned_orders() -> None:
    statement = _base_statement(SimpleNamespace(id=42, role=UserRole.landlord))
    assert "bookings.bm_id" in str(statement)
    assert ":bm_id_1" in str(statement)

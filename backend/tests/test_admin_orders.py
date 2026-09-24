"""管理员订单归档的最终状态与金额展示规则测试。"""
from types import SimpleNamespace

from app.api.v1.routes.admin_orders import (
    FINAL_CANCELLED,
    FINAL_SUCCESS,
    _base_statement,
    _category,
    _latest_payments,
    _payment_amount_minor,
    _row,
)
from app.models.booking import BookingStatus
from app.models.user import UserRole


def test_only_real_final_statuses_are_archived() -> None:
    assert FINAL_SUCCESS == {BookingStatus.contract_signed, BookingStatus.completed}
    assert FINAL_CANCELLED == {
        BookingStatus.cancelled,
        BookingStatus.rejected,
        BookingStatus.payment_expired,
    }
    assert BookingStatus.paid not in FINAL_SUCCESS | FINAL_CANCELLED
    assert BookingStatus.contract_signed in FINAL_SUCCESS
    assert BookingStatus.payment_pending not in FINAL_SUCCESS | FINAL_CANCELLED


def test_final_status_categories_use_frontend_values() -> None:
    assert _category(BookingStatus.completed) == "completed"
    assert _category(BookingStatus.contract_signed) == "completed"
    assert _category(BookingStatus.paid) == "active"
    assert _category(BookingStatus.contract_ready) == "active"
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
    assert "institutes.bm_id" in str(statement)


def test_admin_order_row_prefers_tenant_profile_contact() -> None:
    booking = SimpleNamespace(
        id=1,
        tenant=SimpleNamespace(chinese_name="张三", given_name_pinyin=None, surname_pinyin=None, preferred_name=None, phone="13671721835"),
        user=SimpleNamespace(username="tenant_account", phone="19900000000"),
        unit_type=None,
        institute=None,
        room_number=None,
        scheduled_date=None,
        lease_months=None,
        contract_start=None,
        contract_end=None,
        status=BookingStatus.paid,
        created_at=None,
        updated_at=None,
        total_rent=None,
        deposit_amount=None,
        deposit_status="unpaid",
    )

    row = _row(booking, None)

    assert row["tenant_name"] == "张三"
    assert row["phone"] == "13671721835"


def test_admin_order_row_falls_back_to_user_contact() -> None:
    booking = SimpleNamespace(
        id=1,
        tenant=None,
        user=SimpleNamespace(username="tenant_account", phone="19900000000"),
        unit_type=None,
        institute=None,
        room_number=None,
        scheduled_date=None,
        lease_months=None,
        contract_start=None,
        contract_end=None,
        status=BookingStatus.paid,
        created_at=None,
        updated_at=None,
        total_rent=None,
        deposit_amount=None,
        deposit_status="unpaid",
    )

    row = _row(booking, None)

    assert row["tenant_name"] == "tenant_account"
    assert row["phone"] == "19900000000"

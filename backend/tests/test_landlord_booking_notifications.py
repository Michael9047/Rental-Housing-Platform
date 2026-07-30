"""支付成功后的房东邮件与站内通知测试。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.booking import BookingStatus
from app.models.notification import NotificationOutboxStatus
from app.models.payment import PaymentStatus
from app.services.email_templates import render
from app.services.order_notification_service import OrderNotificationService
from app.services.payment_service import PaymentOrderService
from app.tasks.outbox_tasks import record_delivery_failure


def make_booking(status=BookingStatus.paid):
    return SimpleNamespace(id=42, property_id=8, status=status, scheduled_date="2026-08-01", lease_months=12)


def make_payment(status=PaymentStatus.success):
    return SimpleNamespace(
        id="pay-42", status=status, paid_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
        settlement_currency="GBP", settlement_amount_minor=100000,
        cny_reference_amount_minor=920000, property_currency="GBP",
        snapshot={"commencement_date":"2026-08-01","expiry_date":"2027-08-01","tenancy_months":12,
                  "agreement_number":"C-42","tenant_name":"测试租客",
                  "fees":{"current_total":{"currency":"GBP","decimal":"1000.00"}}},
    )


def make_property():
    return SimpleNamespace(id=8, landlord_id=9, title="测试公寓", address="测试地址", property_type=SimpleNamespace(value="apartment"))


@pytest.mark.asyncio
async def test_paid_webhook_event_enqueues_landlord_once():
    session=Mock(); session.scalar=AsyncMock(return_value=None)
    landlord=SimpleNamespace(id=9,username="房东",email="landlord@example.test",email_verified=True)
    session.get=AsyncMock(side_effect=[make_property(),landlord])
    row=await OrderNotificationService(session).enqueue_landlord_booking_confirmed(make_booking(),make_payment(),contract=SimpleNamespace(agreement_number="C-42"))
    assert row.event_key=="landlord-booking-confirmed:42:pay-42"
    assert row.event_type=="LANDLORD_BOOKING_CONFIRMED" and row.recipient_email==landlord.email
    assert row.status==NotificationOutboxStatus.pending and row.retryable is True
    assert len(session.add_all.call_args.args[0])==2


@pytest.mark.asyncio
async def test_duplicate_webhook_does_not_enqueue_twice():
    session=Mock(); session.scalar=AsyncMock(return_value=SimpleNamespace(event_key="landlord-booking-confirmed:42:pay-42"))
    result=await OrderNotificationService(session).enqueue_landlord_booking_confirmed(make_booking(),make_payment())
    assert result is None and not session.add_all.called


@pytest.mark.asyncio
@pytest.mark.parametrize("booking_status,payment_status",[
    (BookingStatus.payment_failed,PaymentStatus.failed),
    (BookingStatus.payment_processing,PaymentStatus.processing),
    (BookingStatus.payment_expired,PaymentStatus.expired),
])
async def test_non_paid_states_never_enqueue_success_notice(booking_status,payment_status):
    session=Mock()
    assert await OrderNotificationService(session).enqueue_landlord_booking_confirmed(make_booking(booking_status),make_payment(payment_status)) is None
    session.scalar.assert_not_called()


@pytest.mark.asyncio
async def test_unverified_landlord_email_creates_failed_record_and_admin_alert():
    session=Mock(); session.scalar=AsyncMock(return_value=None); session.scalars=AsyncMock(return_value=[SimpleNamespace(id=99)])
    landlord=SimpleNamespace(id=9,username="房东",email="unverified@example.test",email_verified=False)
    session.get=AsyncMock(side_effect=[make_property(),landlord])
    row=await OrderNotificationService(session).enqueue_landlord_booking_confirmed(make_booking(),make_payment(),contract=SimpleNamespace(agreement_number="C-42"))
    assert row.status==NotificationOutboxStatus.failed and row.retryable is False
    assert row.recipient_email is None and row.last_error=="LANDLORD_EMAIL_NOT_VERIFIED"
    assert session.add.called


def test_email_failure_is_retryable_with_backoff():
    row=SimpleNamespace(attempts=0,status=NotificationOutboxStatus.processing,last_error=None,next_attempt_at=None)
    now=datetime(2026,7,22,tzinfo=timezone.utc)
    record_delivery_failure(row,RuntimeError("mailpit unavailable"),now)
    assert row.attempts==1 and row.status==NotificationOutboxStatus.failed
    assert row.next_attempt_at>now


def test_landlord_email_contains_no_sensitive_tenant_data():
    context={"event_title":"【房屋已成功预订】订单 42 / Property Booking Confirmed","user_name":"房东","order_number":"42","property_id":8,"property_name":"测试公寓","property_address":"测试地址","room_type":"apartment","move_in_date":"2026-08-01","expiry_date":"2027-08-01","tenancy_months":12,"settlement_amount":"GBP 1000.00","cny_reference_amount":"CNY 9200.00","property_reference_amount":"GBP 1000.00","paid_at":"2026-07-22T00:00:00Z","contract_number":"C-42","tenant_name":"测试租客","order_url":"http://localhost/landlord/bookings/42","property_manage_url":"http://localhost/manage/properties/8","support_email":"support@example.test"}
    html=render("landlord_booking_confirmed",**context)
    lowered=html.lower()
    assert "passport" not in lowered and "signature" not in lowered and "cvv" not in lowered and "token=" not in lowered


@pytest.mark.asyncio
async def test_verified_success_webhook_is_the_trigger_for_landlord_notice():
    session=Mock(); session.scalar=AsyncMock(); session.commit=AsyncMock(); session.refresh=AsyncMock()
    booking=SimpleNamespace(id=42,property_id=8,status=BookingStatus.payment_processing,deposit_status="unpaid",payment_transaction_id=None,inventory_reserved=True)
    payment=make_payment(); payment.status=PaymentStatus.processing; payment.booking_id=42; payment.provider_payment_id="provider-pay-42"; payment.expires_at=datetime(2026,7,23,tzinfo=timezone.utc)
    property_obj=SimpleNamespace(status="available")
    session.scalar.side_effect=[None,payment,booking,payment,property_obj]
    service=PaymentOrderService(session)
    service.provider.verify_webhook=Mock(return_value={"event_id":"evt-success","provider_payment_id":"provider-pay-42","status":"succeeded","transaction_id":"txn-42"})
    service.validate_event=Mock()
    with patch.object(OrderNotificationService,"enqueue",new=AsyncMock()), patch.object(OrderNotificationService,"enqueue_landlord_booking_confirmed",new=AsyncMock()) as landlord_enqueue:
        await service.process_webhook(b"signed-provider-payload","valid-signature")
    assert booking.status==BookingStatus.paid and payment.status==PaymentStatus.success
    landlord_enqueue.assert_awaited_once_with(booking,payment)

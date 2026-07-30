"""支付订单状态、边界到期和迟到回调规则测试。"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.booking import BookingStatus
from app.services.payment_service import PaymentOrderService


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("source,target", [
    (BookingStatus.contract_signed, BookingStatus.payment_pending),
    (BookingStatus.payment_pending, BookingStatus.payment_processing),
    (BookingStatus.payment_processing, BookingStatus.paid),
    (BookingStatus.payment_processing, BookingStatus.payment_failed),
    (BookingStatus.payment_failed, BookingStatus.payment_pending),
])
def test_backend_controlled_transitions_write_audit(source, target):
    session = Mock(); service = PaymentOrderService(session)
    booking = Mock(id=10, status=source)
    service._transition(booking, target, reason="test", payment_id="pay-1")
    assert booking.status == target
    audit = session.add.call_args.args[0]
    assert audit.details["from"] == source.value and audit.details["to"] == target.value


def test_paid_never_expires_and_repeated_expiry_is_idempotent():
    assert not PaymentOrderService.should_expire(BookingStatus.paid, None, True)
    assert not PaymentOrderService.should_expire(BookingStatus.payment_expired, None, False)


def test_failed_and_pending_expire_when_unpaid():
    assert PaymentOrderService.should_expire(BookingStatus.payment_pending, None, False)
    assert PaymentOrderService.should_expire(BookingStatus.payment_failed, None, False)


def test_processing_requires_provider_check_before_expiration():
    assert not PaymentOrderService.should_expire(BookingStatus.payment_processing, "processing", False)
    assert not PaymentOrderService.should_expire(BookingStatus.payment_processing, "succeeded", False)
    assert PaymentOrderService.should_expire(BookingStatus.payment_processing, "pending", False)


def test_success_before_deadline_becomes_paid():
    assert PaymentOrderService.webhook_target(BookingStatus.payment_processing, "succeeded", NOW, NOW + timedelta(seconds=1)) == BookingStatus.paid


def test_failure_remains_retryable_before_deadline():
    assert PaymentOrderService.webhook_target(BookingStatus.payment_processing, "failed", NOW, NOW + timedelta(hours=1)) == BookingStatus.payment_failed


def test_exact_deadline_and_late_success_go_to_review():
    assert PaymentOrderService.webhook_target(BookingStatus.payment_processing, "succeeded", NOW, NOW) == BookingStatus.payment_review
    assert PaymentOrderService.webhook_target(BookingStatus.payment_expired, "succeeded", NOW, NOW - timedelta(seconds=1)) == BookingStatus.payment_review


def test_expiration_releases_inventory_flag_by_policy():
    booking = Mock(status=BookingStatus.payment_processing, inventory_reserved=True)
    assert PaymentOrderService.should_expire(booking.status, "pending", False)
    PaymentOrderService.release_inventory(booking)
    assert booking.inventory_reserved is False


def test_success_expiry_race_has_no_path_from_paid_to_expired():
    # webhook 先取得行锁并提交 paid 后，到期任务必须幂等跳过。
    assert not PaymentOrderService.should_expire(BookingStatus.paid, None, True)
    # 到期任务先提交后，迟到成功只能进入人工核对，不能静默恢复预订。
    assert PaymentOrderService.webhook_target(BookingStatus.payment_expired, "succeeded", NOW, NOW) == BookingStatus.payment_review


@pytest.mark.asyncio
async def test_duplicate_webhook_returns_existing_payment_without_transition():
    session = Mock(); session.scalar = AsyncMock()
    service = PaymentOrderService(session)
    existing_event = Mock(); payment = Mock(id="pay-1")
    session.scalar.side_effect = [existing_event, payment]
    service.provider.verify_webhook = Mock(return_value={"event_id": "evt-repeat", "provider_payment_id": "pi-1"})
    result = await service.process_webhook(b"{}", "valid")
    assert result is payment
    session.commit.assert_not_called()

"""个人中心订单权限、支付按钮状态、倒计时和金额校验测试。"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus
from app.services.tenant_order_service import TenantOrderService
from app.schemas.payment import TenantOrderListResponse


def fixtures(*, booking_status=BookingStatus.payment_pending, payment_status=PaymentStatus.pending, hours=2, reserved=True):
    now = datetime.now(timezone.utc)
    booking = SimpleNamespace(
        id=21, tenant_id=7, status=booking_status, inventory_reserved=reserved,
        payment_expires_at=now + timedelta(hours=hours),
    )
    payment = SimpleNamespace(
        id="pay-21", booking_id=21, status=payment_status,
        expires_at=now + timedelta(hours=hours), settlement_currency="CNY",
        settlement_amount_minor=10000,
        snapshot={"fees":{"current_total":{"currency":"CNY","minor_units":10000}}},
        created_at=now,
    )
    contract = SimpleNamespace(id="agreement-21")
    signature = SimpleNamespace(agreement_id="agreement-21")
    return booking, payment, contract, signature


async def eligibility(**kwargs):
    booking, payment, contract, signature = fixtures(**kwargs)
    session = AsyncMock()
    session.scalar.side_effect = [booking, payment, contract, signature, None]
    return await TenantOrderService(session).payment_eligibility(21, 7)


@pytest.mark.asyncio
async def test_pending_order_can_pay_before_deadline():
    result = await eligibility()
    assert result.can_pay is True and result.payment_status == "payment_pending"


@pytest.mark.asyncio
async def test_signed_booking_before_first_payment_attempt_is_still_payable_order():
    booking, _, contract, signature = fixtures()
    session = AsyncMock()
    session.scalar.side_effect = [booking, None, contract, signature, None]
    result = await TenantOrderService(session).payment_eligibility(21, 7)
    assert result.can_pay is True
    assert result.payment_status == "payment_pending"
    assert result.payment_id is None


@pytest.mark.asyncio
async def test_failed_order_can_retry_before_deadline():
    result = await eligibility(booking_status=BookingStatus.payment_failed, payment_status=PaymentStatus.failed)
    assert result.can_pay is True and result.payment_status == "payment_failed"


@pytest.mark.asyncio
async def test_processing_order_cannot_create_another_payment():
    booking, payment, contract, signature = fixtures(
        booking_status=BookingStatus.payment_processing,
        payment_status=PaymentStatus.processing,
    )
    session = AsyncMock()
    session.scalar.side_effect = [booking, payment, contract, signature, "processing-payment"]
    result = await TenantOrderService(session).payment_eligibility(21, 7)
    assert result.can_pay is False
    assert "不允许支付" in result.reason or "请勿重复支付" in result.reason


@pytest.mark.asyncio
async def test_expired_or_released_order_cannot_pay():
    expired = await eligibility(hours=-1)
    released = await eligibility(reserved=False)
    assert expired.can_pay is False and "期限已过" in expired.reason
    assert released.can_pay is False and "预留已失效" in released.reason


@pytest.mark.asyncio
async def test_amount_or_currency_change_blocks_payment():
    booking, payment, contract, signature = fixtures()
    payment.settlement_amount_minor = 9999
    session = AsyncMock()
    session.scalar.side_effect = [booking, payment, contract, signature, None]
    result = await TenantOrderService(session).payment_eligibility(21, 7)
    assert result.can_pay is False and "金额或币种" in result.reason


@pytest.mark.asyncio
async def test_other_tenant_cannot_validate_order():
    session = AsyncMock()
    session.scalar.return_value = None
    with pytest.raises(LookupError):
        await TenantOrderService(session).payment_eligibility(21, 999)
    statement = session.scalar.await_args.args[0]
    assert "bookings.tenant_id" in str(statement)


def test_masked_contact_never_returns_complete_values():
    service = TenantOrderService(AsyncMock())
    assert service._mask_phone("+8613212341770") == "+86 132****1770"
    assert service._mask_email("wang@example.com") == "w***@example.com"


def test_empty_order_collection_is_http_200_shape():
    response=TenantOrderListResponse(items=[],total=0)
    assert response.model_dump()=={"items":[],"total":0}

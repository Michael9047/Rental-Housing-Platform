"""验证测试支付服务商验签和关键字段核对。"""
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.payment_provider import (
    MockHostedPaymentProvider, PaymentMethod, PaymentProvider, PaymentRequest,
    provider_availability, redact_payment_log_data,
)
from app.services.payment_service import PaymentOrderService
from app.schemas.payment import PaymentCreate
from app.models.booking import BookingStatus
from unittest.mock import AsyncMock, Mock, patch


def event() -> dict:
    return {"event_id":"evt_1", "provider_payment_id":"pi_1", "merchant_account":"mock_test_account", "order_number":"order_1", "amount_minor":12345, "currency":"CNY", "status":"succeeded"}


def payment():
    return SimpleNamespace(provider_payment_id="pi_1", provider_merchant_account="mock_test_account", out_trade_no="order_1", settlement_amount_minor=12345, settlement_currency="CNY")


def test_mock_webhook_signature_rejects_tampering():
    provider = MockHostedPaymentProvider(); raw = json.dumps(event()).encode(); signature = provider.sign(raw)
    assert provider.verify_webhook(raw, signature)["event_id"] == "evt_1"
    with pytest.raises(ValueError, match="signature"):
        provider.verify_webhook(raw + b" ", signature)


def test_checkout_creation_is_stable_for_same_payment():
    provider = MockHostedPaymentProvider()
    first = provider.create_checkout("payment-123")
    second = provider.create_checkout("payment-123")
    assert first == second
    assert first.checkout_url.startswith("/api/v1/payments/mock-checkout/")


@pytest.mark.parametrize("field,value", [("amount_minor", 1), ("currency", "USD"), ("merchant_account", "other"), ("order_number", "other"), ("provider_payment_id", "other")])
def test_webhook_rejects_mismatched_payment_fields(field, value):
    data = event(); data[field] = value
    with pytest.raises(ValueError, match="不匹配"):
        PaymentOrderService.validate_event(data, payment())


def test_webhook_accepts_exact_server_amount():
    PaymentOrderService.validate_event(event(), payment())


def test_frontend_cannot_supply_payment_amount():
    with pytest.raises(ValidationError):
        PaymentCreate.model_validate({"booking_id": 1, "amount": 1})


def test_provider_exposes_complete_multi_provider_contract():
    required={"create_payment","query_payment","verify_webhook","close_payment","refund_payment","query_refund"}
    assert required <= set(PaymentProvider.__abstractmethods__)


def test_mock_qr_is_dynamic_per_server_payment_attempt():
    provider=MockHostedPaymentProvider(PaymentMethod.WECHAT_PAY)
    def request(attempt): return PaymentRequest("PAY-1",attempt,1234,"CNY","2026-07-23T00:00:00Z",attempt,"booking")
    first=provider.create_payment(request("attempt-11111111")); second=provider.create_payment(request("attempt-22222222"))
    assert first.checkout_url != second.checkout_url and first.qr_code_url == first.checkout_url


def test_development_availability_is_explicit_test_mode():
    methods=provider_availability()
    assert {item.method for item in methods}==set(PaymentMethod)
    assert all(item.available and item.test_mode for item in methods)


def test_production_without_live_switch_is_not_available():
    settings=SimpleNamespace(environment="production",payments_live_enabled=False)
    with patch("app.services.payment_provider.get_settings",return_value=settings):
        methods=provider_availability()
    assert all(not item.available and not item.test_mode and item.reason=="暂未开通" for item in methods)


def test_payment_log_redaction_hides_keys_and_card_like_values():
    safe=redact_payment_log_data({"api_key":"secret","cvv":"123","message":"card 4242424242424242"})
    assert safe["api_key"]=="[REDACTED]" and safe["cvv"]=="[REDACTED]"
    assert "4242424242424242" not in safe["message"]


@pytest.mark.asyncio
async def test_unsigned_contract_cannot_create_payment():
    session=Mock(); session.scalar=AsyncMock()
    booking=SimpleNamespace(id=1,tenant_id=7,status=BookingStatus.contract_ready,payment_expires_at=None,deposit_status="unpaid")
    session.scalar.side_effect=[None,booking,None]
    with pytest.raises(RuntimeError,match="签署"):
        await PaymentOrderService(session).create(1,7,"idem-unsigned","租客")


@pytest.mark.asyncio
async def test_repeated_create_returns_same_payment_for_idempotency_key():
    session=Mock(); existing=SimpleNamespace(id="same",booking_id=1,user_id=7)
    session.scalar=AsyncMock(return_value=existing)
    result=await PaymentOrderService(session).create(1,7,"same-key","租客")
    assert result is existing
    session.commit.assert_not_called()

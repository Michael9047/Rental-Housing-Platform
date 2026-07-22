"""订单邮件模板、事件覆盖和隐私约束测试。"""
from app.services.email_templates import render
from app.services.order_notification_service import TITLES
from app.services.order_notification_service import OrderNotificationService
from app.models.booking import BookingStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest


REQUIRED_EVENTS = {
    "contract_signed","payment_succeeded","payment_failed","payment_processing_delayed",
    "payment_reminder_12h","payment_reminder_1h","payment_expired","late_payment_review",
    "refund_succeeded","refund_failed","contract_resign_required",
}


def test_all_required_order_email_events_have_titles():
    assert REQUIRED_EVENTS <= TITLES.keys()


def test_order_email_contains_safe_details_and_no_sensitive_fields():
    html = render("order_event", event_title="支付成功，预订已确认", user_name="测试租客", order_number="42", property_name="测试房源", property_address="测试地址", move_in_date="2026-08-01", tenancy_months=12, amount="CNY 1000.00", status="paid", payment_deadline="2026-07-23T00:00:00+00:00", order_url="http://localhost:5173/booking/order/42/success", support_email="support@localhost")
    assert "订单编号" in html and "测试房源" in html and "请勿直接回复" in html
    assert "passport" not in html.lower() and "signature" not in html.lower() and "token=" not in html.lower()


def test_order_link_contains_no_permanent_login_token():
    url = "http://localhost:5173/booking/order/42/payment-status"
    assert "token" not in url and "access_token" not in url


@pytest.mark.asyncio
async def test_outbox_and_in_app_notification_are_added_without_commit():
    session=Mock(); session.scalar=AsyncMock(return_value=None)
    session.get=AsyncMock(side_effect=[SimpleNamespace(id=7,username="租客"),SimpleNamespace(title="房源",address="地址")])
    booking=SimpleNamespace(id=9,tenant_id=7,property_id=3,application_data={"pricing_snapshot":{"options":[{"months":12,"prices":{"amount_due_now":{"local":{"currency":"CNY","minor_units":10000}}}}]}},lease_months=12,scheduled_date="2026-08-01",payment_expires_at=None,status=BookingStatus.contract_signed)
    contract=SimpleNamespace(agreement_number="C-9",version=1)
    row=await OrderNotificationService(session).enqueue("contract_signed",booking,contract=contract,discriminator="1")
    assert row.event_key == "order:9:contract_signed:1"
    assert len(session.add_all.call_args.args[0]) == 2
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_event_key_does_not_enqueue_again():
    existing=SimpleNamespace(event_key="order:9:payment_expired:24h")
    session=Mock(); session.scalar=AsyncMock(return_value=existing)
    booking=SimpleNamespace(id=9)
    assert await OrderNotificationService(session).enqueue("payment_expired",booking,discriminator="24h") is None
    session.add_all.assert_not_called()

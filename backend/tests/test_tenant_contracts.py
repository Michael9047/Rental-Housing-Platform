"""个人中心合同权限、分类边界、房源时区和安全下载状态测试。"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus
from app.models.property import CountryCode
from app.services.tenant_contract_service import TenantContractService
from app.schemas.contract import TenantContractListResponse


def objects(*, booking_status=BookingStatus.payment_pending, payment_status=PaymentStatus.processing, end_days=365, contract_status="signed"):
    today=date.today(); start=today+timedelta(days=10); end=today+timedelta(days=end_days)
    booking=SimpleNamespace(id=5,status=booking_status,scheduled_date=start.isoformat(),lease_months=12,payment_expires_at=datetime.now(timezone.utc)+timedelta(hours=12),application_data={"pricing_snapshot":{"options":[{"months":12,"end_date":end.isoformat()}]}})
    property_obj=SimpleNamespace(id=8,title="测试房源",address="测试地址",country=CountryCode.CN)
    payment=SimpleNamespace(id="p1",order_id="PAY-1",status=payment_status,snapshot={"commencement_date":start.isoformat(),"expiry_date":end.isoformat(),"fees":{"current_total":{"currency":"CNY","minor_units":10000}}},settlement_currency="CNY",settlement_amount_minor=10000,expires_at=datetime.now(timezone.utc)+timedelta(hours=12),created_at=datetime.now(timezone.utc),paid_at=datetime.now(timezone.utc) if payment_status==PaymentStatus.success else None,transaction_id="mock_txn_success" if payment_status==PaymentStatus.success else None)
    contract=SimpleNamespace(id="c1",agreement_number="A-1",version=1,content_hash="a"*64,booking_id=5,property_id=8,tenant_id=7,status=contract_status,snapshot={},file_path=None,content="locked")
    signature=SimpleNamespace(signed_at=datetime.now(timezone.utc),property_timezone="Asia/Shanghai",signed_pdf_object_key="private/signed.pdf")
    return contract,signature,booking,property_obj,payment


async def item(**kwargs):
    contract,signature,booking,property_obj,payment=objects(**kwargs)
    session=AsyncMock();session.get.side_effect=[booking,property_obj];session.scalar.side_effect=[payment,None]
    return await TenantContractService(session)._item(contract,signature)


@pytest.mark.asyncio
async def test_signed_unpaid_contract_is_pending_not_confirmed():
    result=await item(booking_status=BookingStatus.payment_processing,payment_status=PaymentStatus.processing)
    assert result.category=="pending_effective" and result.reservation_status=="not_confirmed"
    assert "支付处理中" in result.status_labels and result.can_pay is False


@pytest.mark.asyncio
async def test_failed_payment_can_retry_before_deadline():
    result=await item(booking_status=BookingStatus.payment_failed,payment_status=PaymentStatus.failed)
    assert result.category=="pending_effective" and result.can_pay is True
    assert "支付失败，可重试" in result.status_labels


@pytest.mark.asyncio
async def test_paid_contract_expiring_boundary_uses_property_timezone():
    result=await item(booking_status=BookingStatus.paid,payment_status=PaymentStatus.success,end_days=30)
    assert result.category=="expiring_soon" and result.property_timezone=="Asia/Shanghai"
    assert result.reservation_status=="confirmed"


@pytest.mark.asyncio
async def test_category_clock_is_evaluated_in_property_timezone(monkeypatch):
    captured=[]
    monkeypatch.setattr(TenantContractService,"_now",staticmethod(lambda name:(captured.append(name) or datetime(2026,7,22,23,30,tzinfo=timezone.utc))))
    await item(booking_status=BookingStatus.paid,payment_status=PaymentStatus.success,end_days=365)
    assert captured==["Asia/Shanghai"]


@pytest.mark.asyncio
async def test_paid_future_move_in_is_effective_and_waiting():
    result=await item(booking_status=BookingStatus.paid,payment_status=PaymentStatus.success,end_days=365)
    assert result.category=="effective" and result.waiting_for_move_in is True
    assert result.booking_status=="confirmed"
    assert "预订成功" in result.status_labels and "等待入住" in result.status_labels


@pytest.mark.asyncio
async def test_expired_payment_has_specific_reason():
    result=await item(booking_status=BookingStatus.payment_expired,payment_status=PaymentStatus.expired)
    assert result.category=="invalid" and result.invalid_reason=="支付期限已过，预订未生效"


@pytest.mark.asyncio
async def test_other_tenant_cannot_load_contract_detail():
    query_result=SimpleNamespace(first=lambda:None);session=AsyncMock();session.execute.return_value=query_result
    with pytest.raises(LookupError):
        await TenantContractService(session).detail_for_tenant("other-contract",999)
    statement=session.execute.await_args.args[0]
    assert "contracts.tenant_id" in str(statement)


@pytest.mark.asyncio
async def test_payment_review_contract_is_invalid_not_booking_success():
    result=await item(booking_status=BookingStatus.payment_review,payment_status=PaymentStatus.review)
    assert result.category=="invalid" and result.reservation_status=="not_confirmed"


@pytest.mark.asyncio
async def test_signed_pdf_is_only_advertised_as_available_not_public_key():
    result=await item(booking_status=BookingStatus.paid,payment_status=PaymentStatus.success)
    assert result.signed_pdf_available is True
    assert "signed_pdf_object_key" not in result.model_dump()


def test_empty_contract_collection_is_http_200_shape():
    response=TenantContractListResponse(items=[],total=0)
    assert response.model_dump()=={"items":[],"total":0}

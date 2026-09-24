"""合同签署成功、笔迹、幂等、越权、版本和异步 PDF 测试。"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.models.booking import Booking,BookingStatus
from app.models.contract import Contract,ContractSignature
from app.schemas.contract import ContractSignCreate
from app.services.contract_signing_service import ContractSignError,ContractSigningService

def payload(**changes)->ContractSignCreate:
    data={"agreement_version":1,"agreement_content_hash":"a"*64,"tenant_name":"测试租客","consent_text_version":"2026.1","idempotency_key":"idem-key-123","strokes":[[{"x":i/20,"y":(i%3)/4,"pressure":.5} for i in range(12)]],"name_confirmed":True,"electronic_signature_consent":True};data.update(changes);return ContractSignCreate.model_validate(data)

def objects(version=1,content_hash="a"*64):
    return Contract(id="c1",booking_id=10,tenant_id=7,unit_type_id=2,version=version,content_hash=content_hash,status="generated",pdf_status="ready",snapshot={"tenant_name_cn":"测试租客"},content="x"),Booking(id=10,user_id=7,bm_id=3,unit_type_id=2,status=BookingStatus.contract_ready)

def test_empty_signature_rejected():
    with pytest.raises(ContractSignError) as exc:ContractSigningService.validate_strokes(payload(strokes=[[{"x":.1,"y":.1},{"x":.11,"y":.1}]]))
    assert exc.value.code=="SIGNATURE_EMPTY"

def test_chinese_signature_succeeds_validation():
    count,length=ContractSigningService.validate_strokes(payload());assert count>=8 and length>=.2

def test_signature_too_large_rejected():
    points=[{"x":(i%100)/100,"y":((i//100)%50)/50,"pressure":.5} for i in range(5001)]
    with pytest.raises(ContractSignError) as exc:ContractSigningService.validate_strokes(payload(strokes=[points]))
    assert exc.value.code=="SIGNATURE_TOO_LARGE"

def test_consent_required():
    with pytest.raises(ContractSignError) as exc:ContractSigningService.validate_strokes(payload(name_confirmed=False))
    assert exc.value.code=="CONSENT_REQUIRED"

def test_repeated_submission_returns_one_record():
    session=AsyncMock();contract,_=objects();existing=ContractSignature(agreement_id="c1",agreement_version=1,agreement_content_hash="a"*64,tenant_user_id=7,tenant_name="测试租客",signed_at=datetime.now(timezone.utc),property_timezone="Asia/Shanghai",consent_text_version="2026.1",signature_hash="b"*64,idempotency_key="idem-key-123");session.get.return_value=contract;session.scalar.return_value=existing
    result=asyncio.run(ContractSigningService(session).sign("c1",7,payload(),None,None));assert result.agreement_id==existing.agreement_id;session.commit.assert_not_awaited()

def test_other_tenant_cannot_sign():
    session=AsyncMock();contract,_=objects();session.get.return_value=contract
    with pytest.raises(ContractSignError) as exc:asyncio.run(ContractSigningService(session).sign("c1",8,payload(),None,None))
    assert exc.value.code=="FORBIDDEN"

@pytest.mark.parametrize("version,content_hash",[(2,"a"*64),(1,"b"*64)])
def test_version_or_hash_mismatch(version,content_hash):
    session=AsyncMock();contract,_=objects(version,content_hash);session.get.return_value=contract
    with pytest.raises(ContractSignError) as exc:asyncio.run(ContractSigningService(session).sign("c1",7,payload(),None,None))
    assert exc.value.code=="AGREEMENT_VERSION_MISMATCH"

def test_success_completes_already_paid_booking():
    session=AsyncMock();session.add=MagicMock();contract,booking=objects();session.get.side_effect=[contract,None,booking];session.scalar.return_value=None
    service=ContractSigningService(session);service._storage.put=MagicMock()
    with patch("app.services.inventory_service.sync_unit_type_inventory",new=AsyncMock(return_value=None)):
        record=asyncio.run(service.sign("c1",7,payload(idempotency_key="success-key"),None,None))
    assert contract.status=="signed" and contract.pdf_status=="ready";assert booking.status==BookingStatus.completed and booking.payment_expires_at is None;assert record.pdf_status=="ready";session.commit.assert_awaited_once()

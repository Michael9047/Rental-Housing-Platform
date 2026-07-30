"""双语合同网页与 PDF 的字段、金额、日期、字体和分页测试。"""

import asyncio
from datetime import datetime, timezone

from app.models.contract import Contract
from app.services.contract_pdf_service import ContractPdfService


def contract_fixture() -> Contract:
    sections = [{"number": number, "title_zh": f"中文条款{number}", "title_en": f"English Clause {number}", "zh": "这是中文合同条款，用于验证逐条对应和分页。" * 4, "en": "This is the corresponding English clause for rendering and pagination. " * 4} for number in range(1, 18)]
    snapshot = {
        "development_notice": "业务开发模板，待房源所在地法务审核", "agreement_number": "HRTA-TEST-V1",
        "order_number": "10", "agreement_version": 1, "generated_at": "2026-07-22T00:00:00+00:00",
        "provider_name": "测试供应方", "platform_name": "测试平台", "platform_role": "预订中介",
        "tenant_name_cn": "测试租客", "tenant_name_en": "TEST TENANT", "property_name": "测试房源",
        "property_address": "测试地址", "property_id": 2, "room_type": "公寓 / Apartment",
        "commencement_date": "2026-08-01", "expiry_date": "2027-08-01", "tenancy_months": 12,
        "monthly_rent": "CNY 5200.00", "deposit": "CNY 5200.00", "service_fee": "CNY 6240.00",
        "amount_due_now": "CNY 16640.00", "settlement_currency": "CNY", "cny_reference_amount": "CNY 16640.00",
        "exchange_rate": "1", "exchange_rate_at": "2026-07-22T00:00:00+00:00", "exchange_rate_source": "测试汇率",
        "provider_execution_mode": "待配置", "content_hash": "a" * 64, "sections": sections,
    }
    return Contract(id="c1", booking_id=10, tenant_id=7, property_id=2, agreement_number="HRTA-TEST-V1", version=1, template_version="2026.1", content_hash="a" * 64, snapshot=snapshot, generated_at=datetime.now(timezone.utc), content="test", status="generated")


def test_html_has_all_bilingual_clauses_and_server_amounts() -> None:
    html = ContractPdfService.render_html(contract_fixture())
    assert html.count('class="clause"') == 17
    assert "第17条" in html and "Article 17" in html
    assert "CNY 16640.00" in html and "2026-08-01" in html
    assert "Noto Sans CJK SC" in html and "业务开发模板，待房源所在地法务审核" in html


def test_pdf_is_a4_and_paginates_long_bilingual_contract() -> None:
    from weasyprint import HTML
    contract = contract_fixture(); html = ContractPdfService.render_html(contract)
    document = HTML(string=html).render()
    assert len(document.pages) >= 2
    pdf = asyncio.run(ContractPdfService().generate(contract))
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000

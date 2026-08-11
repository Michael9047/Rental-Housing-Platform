"""验证平台预订金不受房源、租期和汇率影响。"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.lease_pricing_service import LeasePricingService


@pytest.mark.asyncio
@pytest.mark.parametrize("months", [3, 6, 9, 12, 24])
async def test_standard_lease_terms_always_charge_fixed_booking_deposit(months: int) -> None:
    unit_type = SimpleNamespace(id=1, base_rent=2410, deposit_amount=999999, currency="SGD", min_stay_months=3)
    quote = SimpleNamespace(rate_to_cny=Decimal("5.268"), quoted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc), source="test")
    settings = SimpleNamespace(booking_deposit_amount_cny=Decimal("2000.00"), booking_deposit_currency="CNY")
    with patch("app.services.lease_pricing_service.ExchangeRateService.quote_to_cny", AsyncMock(return_value=quote)), patch("app.services.lease_pricing_service.get_settings", return_value=settings):
        pricing = await LeasePricingService.calculate(unit_type, "2026-08-17")
    option = next(item for item in pricing.options if item.months == months)
    assert option.prices.booking_deposit.cny.minor_units == 200000
    assert option.prices.amount_due_now.cny.minor_units == 200000
    assert option.prices.rent_total.local.minor_units == 2410 * months * 100


@pytest.mark.asyncio
async def test_deposit_is_fixed_when_property_amount_changes() -> None:
    quote = SimpleNamespace(rate_to_cny=Decimal("1"), quoted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc), source="test")
    settings = SimpleNamespace(booking_deposit_amount_cny=Decimal("2000.00"), booking_deposit_currency="CNY")
    with patch("app.services.lease_pricing_service.ExchangeRateService.quote_to_cny", AsyncMock(return_value=quote)), patch("app.services.lease_pricing_service.get_settings", return_value=settings):
        low = await LeasePricingService.calculate(SimpleNamespace(id=1, base_rent=1, deposit_amount=1, currency="CNY", min_stay_months=3), "2026-08-17")
        high = await LeasePricingService.calculate(SimpleNamespace(id=2, base_rent=999999, deposit_amount=999999, currency="CNY", min_stay_months=3), "2026-08-17")
    assert low.options[0].prices.amount_due_now.cny.minor_units == high.options[0].prices.amount_due_now.cny.minor_units == 200000

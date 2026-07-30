"""入住日期可用性规则测试。"""

from datetime import date
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock

from app.models.property import CountryCode, PropertyStatus
from app.services.booking_availability_service import BookingAvailabilityService


def make_property(**overrides):
    return SimpleNamespace(
        id=10,
        country=overrides.get("country", CountryCode.CN),
        status=overrides.get("status", PropertyStatus.available),
        available_from=overrides.get("available_from"),
        available_until=overrides.get("available_until"),
    )


class BookingTimezoneTests(TestCase):
    def test_country_uses_property_timezone(self) -> None:
        self.assertEqual(
            BookingAvailabilityService.timezone_for_country(CountryCode.CN),
            "Asia/Shanghai",
        )
        self.assertEqual(
            BookingAvailabilityService.timezone_for_country(CountryCode.GB),
            "Europe/London",
        )


class BookingDateValidationTests(IsolatedAsyncioTestCase):
    async def test_past_date_is_rejected_in_property_timezone(self) -> None:
        service = BookingAvailabilityService(AsyncMock())
        service.local_today = lambda _timezone: date(2030, 5, 10)
        valid, reason, timezone_name = await service.validate(
            make_property(), date(2030, 5, 9)
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "入住日期不能早于房源所在地的今天")
        self.assertEqual(timezone_name, "Asia/Shanghai")

    async def test_date_before_available_from_is_rejected(self) -> None:
        service = BookingAvailabilityService(AsyncMock())
        service.local_today = lambda _timezone: date(2030, 5, 1)
        valid, reason, _ = await service.validate(
            make_property(available_from=date(2030, 6, 1)),
            date(2030, 5, 20),
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "入住日期早于房源可入住日期")

    async def test_blocked_date_is_rejected(self) -> None:
        service = BookingAvailabilityService(AsyncMock())
        service.local_today = lambda _timezone: date(2030, 5, 1)
        service.has_conflicting_booking = AsyncMock(return_value=True)
        valid, reason, _ = await service.validate(make_property(), date(2030, 5, 20))
        self.assertFalse(valid)
        self.assertEqual(reason, "该日期已有有效预订，暂不可入住")

    async def test_available_date_is_accepted(self) -> None:
        service = BookingAvailabilityService(AsyncMock())
        service.local_today = lambda _timezone: date(2030, 5, 1)
        service.has_conflicting_booking = AsyncMock(return_value=False)
        valid, reason, _ = await service.validate(make_property(), date(2030, 5, 20))
        self.assertTrue(valid)
        self.assertIsNone(reason)

"""入住日期校验路由的成功、业务错误和异常测试。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.routes.properties import validate_booking_date
from app.schemas.booking_availability import BookingDateValidation
from app.services.booking_availability_service import BookingAvailabilityService


@pytest.fixture
def property_obj() -> SimpleNamespace:
    return SimpleNamespace(id=68)


@pytest.mark.asyncio
async def test_booking_date_validation_success(monkeypatch, property_obj) -> None:
    monkeypatch.setattr(BookingAvailabilityService, "get_property", AsyncMock(return_value=property_obj))
    monkeypatch.setattr(
        BookingAvailabilityService,
        "validate",
        AsyncMock(return_value=(True, None, "Asia/Shanghai")),
    )
    result = await validate_booking_date(
        property_id=68,
        validation=BookingDateValidation(move_in_date=date(2026, 7, 23)),
        session=AsyncMock(),
        _current_user=SimpleNamespace(id=53),
    )
    assert result.model_dump(mode="json") == {
        "available": True,
        "property_id": 68,
        "start_date": "2026-07-23",
        "timezone": "Asia/Shanghai",
        "reason": None,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    ["入住日期不能早于房源所在地的今天", "该日期已有有效预订，暂不可入住"],
)
async def test_booking_date_validation_returns_conflict(monkeypatch, property_obj, reason) -> None:
    monkeypatch.setattr(BookingAvailabilityService, "get_property", AsyncMock(return_value=property_obj))
    monkeypatch.setattr(
        BookingAvailabilityService,
        "validate",
        AsyncMock(return_value=(False, reason, "Asia/Shanghai")),
    )
    with pytest.raises(HTTPException) as exc_info:
        await validate_booking_date(
            property_id=68,
            validation=BookingDateValidation(move_in_date=date(2026, 7, 23)),
            session=AsyncMock(),
            _current_user=SimpleNamespace(id=53),
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == reason


@pytest.mark.asyncio
async def test_booking_date_validation_returns_not_found(monkeypatch) -> None:
    monkeypatch.setattr(BookingAvailabilityService, "get_property", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc_info:
        await validate_booking_date(
            property_id=999999,
            validation=BookingDateValidation(move_in_date=date(2026, 7, 23)),
            session=AsyncMock(),
            _current_user=SimpleNamespace(id=53),
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Property not found"


@pytest.mark.asyncio
async def test_booking_date_validation_propagates_unexpected_error(monkeypatch, property_obj) -> None:
    monkeypatch.setattr(BookingAvailabilityService, "get_property", AsyncMock(return_value=property_obj))
    monkeypatch.setattr(
        BookingAvailabilityService,
        "validate",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )
    with pytest.raises(RuntimeError, match="database unavailable"):
        await validate_booking_date(
            property_id=68,
            validation=BookingDateValidation(move_in_date=date(2026, 7, 23)),
            session=AsyncMock(),
            _current_user=SimpleNamespace(id=53),
        )

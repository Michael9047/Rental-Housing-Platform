"""户型入住日期校验路由测试。"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.routes.unit_types import validate_booking_date


@pytest.mark.asyncio
async def test_booking_date_validation_success() -> None:
    move_in = date.today() + timedelta(days=1)
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(
        has_vacancy=True, available_count=1, available_from=None
    )

    result = await validate_booking_date(68, {"move_in_date": move_in.isoformat()}, session)

    assert result == {"available": True, "reason": None}


@pytest.mark.asyncio
async def test_booking_date_validation_rejects_empty_inventory() -> None:
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(
        has_vacancy=False, available_count=0, available_from=None
    )

    result = await validate_booking_date(
        68, {"move_in_date": (date.today() + timedelta(days=1)).isoformat()}, session
    )

    assert result == {"available": False, "reason": "该户型暂无空房"}


@pytest.mark.asyncio
async def test_booking_date_validation_returns_not_found() -> None:
    session = AsyncMock()
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await validate_booking_date(
            999999,
            {"move_in_date": (date.today() + timedelta(days=1)).isoformat()},
            session,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_booking_date_validation_rejects_invalid_date() -> None:
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(
        has_vacancy=True, available_count=1, available_from=None
    )

    result = await validate_booking_date(68, {"move_in_date": "not-a-date"}, session)

    assert result == {"available": False, "reason": "日期格式不正确"}

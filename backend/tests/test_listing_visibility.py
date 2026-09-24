"""统一房源可见与可预订条件测试。"""
from types import SimpleNamespace

import pytest

from app.models.institute import InstituteStatus
from app.models.unit_type import UnitTypeStatus
from app.services.listing_visibility import is_listable


@pytest.mark.parametrize(
    ("building_status", "unit_status", "deleted", "vacancy", "count", "expected"),
    [
        (InstituteStatus.active, UnitTypeStatus.available, False, True, 1, True),
        (InstituteStatus.offline, UnitTypeStatus.available, False, True, 1, False),
        (InstituteStatus.active, UnitTypeStatus.offline, False, True, 1, False),
        (InstituteStatus.active, UnitTypeStatus.available, True, True, 1, False),
        (InstituteStatus.active, UnitTypeStatus.available, False, False, 1, False),
        (InstituteStatus.active, UnitTypeStatus.available, False, True, 0, False),
    ],
)
def test_is_listable_matrix(building_status, unit_status, deleted, vacancy, count, expected) -> None:
    unit_type = SimpleNamespace(
        status=unit_status,
        deleted_at=object() if deleted else None,
        has_vacancy=vacancy,
        available_count=count,
        institute=SimpleNamespace(status=building_status),
    )
    assert is_listable(unit_type) is expected

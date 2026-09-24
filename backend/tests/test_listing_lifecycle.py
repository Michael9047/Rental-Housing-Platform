"""公寓与户型生命周期状态及发布资料校验测试。"""
from types import SimpleNamespace

from app.models.institute import InstituteStatus
from app.models.unit_type import UnitTypeStatus
from app.services.listing_lifecycle_service import (
    validate_building_publishable,
    validate_unit_type_publishable,
)


def test_offline_statuses_are_distinct_from_recycle_bin() -> None:
    assert InstituteStatus.offline.value == "offline"
    assert InstituteStatus.suspended.value == "suspended"
    assert UnitTypeStatus.offline.value == "offline"


def test_building_publish_validation_reports_exact_missing_fields() -> None:
    building = SimpleNamespace(
        name="测试公寓", country="新加坡", city="新加坡", street="",
        latitude=None, longitude=None,
    )
    result = validate_building_publishable(building, image_count=0)
    assert result.valid is False
    assert result.missing_fields == ("street", "latitude", "longitude", "images")


def test_unit_type_publish_validation_catches_historical_empty_type() -> None:
    unit_type = SimpleNamespace(
        institute_id=254, property_type=None, base_rent=1579, currency="SGD",
        total_count=1, available_count=1, available_from=None, image_urls=["cover.png"],
    )
    result = validate_unit_type_publishable(unit_type)
    assert result.valid is False
    assert result.missing_fields == ("property_type", "available_from")


def test_complete_unit_type_can_be_published() -> None:
    unit_type = SimpleNamespace(
        institute_id=1, property_type="studio", base_rent=1579, currency="SGD",
        total_count=1, available_count=1, available_from="2026-09-01", image_urls=["cover.png"],
    )
    assert validate_unit_type_publishable(unit_type).valid is True

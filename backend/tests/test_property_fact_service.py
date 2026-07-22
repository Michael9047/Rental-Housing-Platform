"""缓存 POI 摘要与批量通勤事实测试。"""
from types import SimpleNamespace

import pytest

from app.services.commute_service import BatchCommuteResult, CommuteResult
from app.services.property_fact_service import (
    CommuteSummary,
    DataCompleteness,
    POISummary,
    PropertyFactBundle,
    PropertyFactService,
    satisfies_poi_requirements,
    summarize_map_poi_data,
)


def test_summarize_cached_map_poi_data() -> None:
    summary, available = summarize_map_poi_data({
        "categories": {
            "bus_station": [{"name": "公交站", "distance": 420}],
            "subway_station": [{"name": "地铁站", "distance": "0.8km"}],
            "supermarket": [
                {"name": "超市A", "distance": 180},
                {"name": "超市B", "distance": 1200},
            ],
            "gym": [{"name": "健身房", "distance": "750m"}],
            "medical": [{"name": "诊所", "distance": 1600}],
        }
    })
    assert summary.nearest_transit_m == 420
    assert summary.nearest_supermarket_m == 180
    assert summary.supermarket_count_1km == 1
    assert summary.nearest_gym_m == 750
    assert summary.medical_count_2km == 1
    assert set(available) == {"transit", "supermarket", "gym", "medical"}


def test_missing_poi_cache_stays_unknown() -> None:
    summary, available = summarize_map_poi_data(None)
    assert summary.nearest_supermarket_m is None
    assert summary.supermarket_count_1km is None
    assert available == []


def test_hard_poi_requirement_requires_known_matching_distance() -> None:
    known = PropertyFactBundle(
        property_id=1,
        poi=POISummary(nearest_supermarket_m=350),
        commute=None,
        data_completeness=DataCompleteness(poi_cache_available=True),
    )
    unknown = PropertyFactBundle(
        property_id=2,
        poi=POISummary(),
        commute=None,
        data_completeness=DataCompleteness(poi_cache_available=False),
    )
    requirement = [{"type": "supermarket", "target_m": 500}]
    assert satisfies_poi_requirements(known, requirement)
    assert not satisfies_poi_requirements(unknown, requirement)


@pytest.mark.asyncio
async def test_batch_commute_preserves_engine_source(monkeypatch) -> None:
    async def fake_calculate(**_kwargs):
        return BatchCommuteResult(results=[
            CommuteResult(
                dest_id=7,
                dist_km=2.5,
                walk_min=30,
                bike_min=10,
                drive_min=8,
                transit_min=15,
                source="ors_api",
            )
        ], source="ors_api")

    monkeypatch.setattr(
        "app.services.property_fact_service.calculate_commute_batch_resilient",
        fake_calculate,
    )
    props = [SimpleNamespace(id=7, latitude=1.3, longitude=103.8)]
    result = await PropertyFactService._load_commutes(
        props, 1.29, 103.77, "SG", None,
    )
    assert result[7] == CommuteSummary(
        dist_km=2.5,
        walk_min=30,
        bike_min=10,
        drive_min=8,
        transit_min=15,
        source="ors_api",
        transit_verified=False,
    )

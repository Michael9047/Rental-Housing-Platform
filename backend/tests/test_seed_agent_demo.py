"""Agent 演示房源目录、POI 与通勤模拟数据测试。"""
from types import SimpleNamespace

from scripts.seed_agent_demo import (
    COMMUTE_BASES,
    MARKETS,
    _simulated_poi_payload,
    validate_demo_catalog,
)


def test_demo_catalog_is_expanded_and_unique() -> None:
    validate_demo_catalog()
    assert len(MARKETS) == 11
    assert sum(len(market["units"]) for market in MARKETS) == 40
    assert sum(len(market["units"]) * 2 for market in MARKETS) == 80
    assert {market["business_id"] for market in MARKETS} == set(COMMUTE_BASES)


def test_each_demo_property_gets_complete_poi_categories() -> None:
    room = SimpleNamespace(id=101)
    content, poi_data, map_poi_data = _simulated_poi_payload(room, MARKETS[0])

    assert set(poi_data) == {"交通", "购物", "医疗", "美食", "生活"}
    assert all(len(entries) >= 2 for entries in poi_data.values())
    assert map_poi_data["source"] == "simulated_demo"
    assert set(map_poi_data["categories"]) == set(poi_data)
    assert "最近公共交通" in content

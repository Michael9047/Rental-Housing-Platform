"""确定性加权评分单测：可复现、优先级改变名次、缺数据中性化"""
from app.services.compare_scoring import (
    PropertyMetrics,
    compute_scores,
    format_commute,
    nearest_transit_meters,
    normalize_priority,
    parse_distance_meters,
)


def test_parse_distance_meters() -> None:
    assert parse_distance_meters("500m") == 500
    assert parse_distance_meters("1km") == 1000
    assert parse_distance_meters("1.2公里") == 1200
    assert parse_distance_meters("约800米") == 800
    assert parse_distance_meters(None) is None
    assert parse_distance_meters("步行可达") is None


def test_nearest_transit_meters_picks_min() -> None:
    poi_data = {
        "交通": [
            {"name": "地铁站A", "distance": "1km"},
            {"name": "公交站B", "distance": "300m"},
        ],
        "购物": [{"name": "商场", "distance": "100m"}],  # 非交通类目不参与
    }
    assert nearest_transit_meters(poi_data) == 300
    assert nearest_transit_meters(None) is None
    assert nearest_transit_meters({"交通": []}) is None


def test_scores_are_deterministic_and_reproducible() -> None:
    metrics = [
        PropertyMetrics(property_id=1, price=2000, area=20, transit_meters=300, rating=4.5, review_count=10),
        PropertyMetrics(property_id=2, price=4000, area=80, transit_meters=1500, rating=3.5, review_count=4),
    ]
    first = compute_scores(metrics, "balanced")
    second = compute_scores(metrics, "balanced")
    assert first == second  # 同数据同优先级 → 同分，可复现


def test_priority_changes_winner() -> None:
    # 房源1：便宜、近地铁、小；房源2：贵、远、大
    metrics = [
        PropertyMetrics(property_id=1, price=2000, area=20, transit_meters=300),
        PropertyMetrics(property_id=2, price=4000, area=80, transit_meters=2500),
    ]
    budget = compute_scores(metrics, "budget")
    space = compute_scores(metrics, "space")

    assert budget[1]["total"] > budget[2]["total"]  # 预算优先 → 便宜的赢
    assert space[2]["total"] > space[1]["total"]    # 空间优先 → 大的赢


def test_missing_data_gets_neutral_score() -> None:
    metrics = [
        PropertyMetrics(property_id=1, price=3000),  # 无面积/无POI/无评价
        PropertyMetrics(property_id=2, price=2000, area=50, transit_meters=400, rating=5.0),
    ]
    scores = compute_scores(metrics, "balanced")
    b1 = scores[1]["breakdown"]
    assert b1["commute"] == 60 and b1["space"] == 60 and b1["rating"] == 60


def test_normalize_priority_falls_back_to_balanced() -> None:
    assert normalize_priority("budget") == "budget"
    assert normalize_priority("whatever") == "balanced"
    assert normalize_priority(None) == "balanced"


def test_format_commute() -> None:
    assert format_commute(500) == "最近交通站点约500m"
    assert format_commute(1500) == "最近交通站点约1.5km"
    assert format_commute(None) is None

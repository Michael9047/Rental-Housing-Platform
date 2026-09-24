"""验证 AI 找房会把多轮累计条件用于召回、过滤和重排。"""
from __future__ import annotations

import inspect
from datetime import date
from types import SimpleNamespace

from app.services.agentic.agents.search_agent import (
    _build_accumulated_semantic_query,
    _select_and_rerank_candidates,
)
from app.services.agentic.query_understanding import QueryUnderstanding
from app.services.property_service import PropertyService


def _candidate(
    candidate_id: int,
    *,
    price: float = 1100,
    commute_minutes: int = 15,
    market_distance: int = 300,
) -> dict:
    institute = SimpleNamespace(
        id=candidate_id + 100,
        name=f"Residence {candidate_id}",
        name_cn=None,
        district="Camden",
        city="London",
        country="GB",
        address="Test Road",
        description="安静的学生公寓",
        amenities=["健身房"],
        female_only=False,
    )
    unit_type = SimpleNamespace(
        id=candidate_id,
        name="Studio",
        description="采光良好",
        base_rent=price,
        currency="GBP",
        bedrooms=0,
        bathrooms=1,
        area_sqm=25,
        amenities=["独立卫浴"],
        min_stay_months=6,
        available_from=date(2026, 9, 1),
        image_urls=["https://example.test/room.jpg"],
    )
    return {
        "unit_type": unit_type,
        "institute": institute,
        "available_rooms": 2,
        "embedding_score": 0.8,
        "_commute_minutes": commute_minutes,
        "_commute_source": "test",
        "_poi_distances": {"market": market_distance},
        "_poi_score": 80,
    }


def test_accumulated_semantic_query_contains_previous_requirements() -> None:
    understanding = QueryUnderstanding(
        rewritten_query="继续推荐，但保留当前条件",
    )
    query = _build_accumulated_semantic_query(
        "继续推荐",
        {
            "institution": "UCL",
            "price_max": 1200,
            "amenities": ["健身房", "独立卫浴"],
            "commute_mode": "walking",
            "commute_minutes": 20,
        },
        understanding,
    )

    assert "继续推荐，但保留当前条件" in query
    assert "UCL" in query
    assert "1200" in query
    assert "健身房" in query
    assert "20" in query


def test_candidate_selection_applies_all_accumulated_hard_constraints() -> None:
    filters = {
        "country": "GB",
        "currency": "GBP",
        "price_max": 1200,
        "amenities": ["健身房", "独立卫浴"],
        "commute_minutes": 20,
        "poi_requirements": [{"type": "market", "max_distance_m": 500}],
        "hard_filters": ["amenities", "commute_minutes", "poi_requirements"],
    }
    matching = _candidate(1)
    commute_too_long = _candidate(2, commute_minutes=35)
    market_too_far = _candidate(3, market_distance=900)

    selected, effective_filters, relaxation_trace, relaxation_level = (
        _select_and_rerank_candidates(
            [matching, commute_too_long, market_too_far],
            filters=filters,
            semantic_query="UCL 附近预算 1200 健身房 独立卫浴 步行 20 分钟",
            min_results=3,
        )
    )

    assert [item["unit_type"].id for item in selected] == [1]
    assert effective_filters == filters
    assert relaxation_level == 0
    assert all(not item.get("applied") for item in relaxation_trace)
    assert selected[0]["_score_breakdown"]["constraint"] == 100.0


def test_property_service_accepts_database_vector_recall() -> None:
    signature = inspect.signature(PropertyService.search_unit_types)

    assert "query_vec" in signature.parameters

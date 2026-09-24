"""AI 推荐卡周边 POI 响应契约测试。"""
from app.api.v1.routes import agent as agent_routes
from app.schemas.property import PropertySearchResult


def test_recommendation_preserves_poi_distances_in_response_and_history(
    monkeypatch,
) -> None:
    property_result = PropertySearchResult(
        id=546,
        unit_type_id=546,
        name="测试户型",
    )
    monkeypatch.setattr(
        agent_routes,
        "_to_search_result",
        lambda _unit_type: property_result,
    )
    recommendation = {
        "property_id": 546,
        "property": object(),
        "poi_distances": {"metro": 69, "market": 28},
    }

    response = agent_routes._recommendation(recommendation).model_dump(mode="json")
    history = agent_routes._serialize_meta({"recommendations": [recommendation]})

    assert response["poi_distances"] == {"metro": 69, "market": 28}
    assert history["recommendations"][0]["poi_distances"] == {
        "metro": 69,
        "market": 28,
    }

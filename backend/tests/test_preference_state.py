"""偏好状态 reducer 单元测试。"""
from app.services.preference_state import (
    apply_explicit_filters,
    apply_preference_operations,
    build_preference_views,
    flatten_preference_state,
)


def test_preference_operations_support_add_update_remove_and_clear() -> None:
    state = apply_preference_operations(None, [
        {"op": "set", "field": "price_max", "value": 3000, "strength": "hard"},
        {"op": "add", "field": "amenities", "value": "阳台", "strength": "soft"},
        {
            "op": "add",
            "field": "poi_requirements",
            "value": {"type": "超市", "target_m": 500, "acceptable_m": 1200},
            "strength": "soft",
        },
    ])
    assert state["filters"]["price_max"] == 3000
    assert state["filters"]["amenities"] == ["阳台"]
    assert state["filters"]["poi_requirements"][0]["type"] == "supermarket"

    state = apply_preference_operations(state, [
        {"op": "update", "field": "price_max", "value": 3500, "strength": "hard"},
        {"op": "update", "field": "poi_requirements", "value": {"type": "supermarket", "target_m": 300}, "strength": "soft"},
        {"op": "remove", "field": "amenities", "value": "阳台"},
    ])
    assert state["filters"]["price_max"] == 3500
    assert "amenities" not in state["filters"]
    assert state["filters"]["poi_requirements"] == [
        {"type": "supermarket", "target_m": 300, "acceptable_m": 600}
    ]

    state = apply_preference_operations(state, [{"op": "clear"}])
    assert state["filters"] == {}
    assert state["constraints"] == []


def test_hard_and_soft_views_keep_mixed_list_strength() -> None:
    state = apply_preference_operations(None, [
        {"op": "add", "field": "amenities", "value": "独立卫浴", "strength": "hard"},
        {"op": "add", "field": "amenities", "value": "阳台", "strength": "soft", "weight": 0.7},
        {"op": "set", "field": "price_max", "value": 3000, "strength": "soft"},
    ])
    payload = flatten_preference_state(state)
    views = build_preference_views(payload)

    assert views.hard_values["amenities"] == ["独立卫浴"]
    assert "price_max" not in views.hard_values
    assert {item["value"] for item in views.soft_constraints if item["field"] == "amenities"} == {"阳台"}


def test_explicit_frontend_filters_override_as_hard_constraints() -> None:
    state = apply_preference_operations(None, [
        {"op": "set", "field": "price_max", "value": 3500, "strength": "soft"},
    ])
    state = apply_explicit_filters(state, {"price_max": 2800, "district": "SIP"})
    views = build_preference_views(flatten_preference_state(state))

    assert views.all_values["price_max"] == 2800
    assert views.hard_values["price_max"] == 2800
    assert views.hard_values["district"] == "SIP"


def test_legacy_flat_filters_are_backward_compatible() -> None:
    views = build_preference_views({
        "price_max": 3000,
        "amenities": ["独立卫浴"],
        "hard_filters": ["amenities"],
        "soft_preferences": ["price"],
    })
    assert views.hard_values["amenities"] == ["独立卫浴"]
    assert "price_max" not in views.hard_values
    assert any(item["field"] == "price_max" for item in views.soft_constraints)

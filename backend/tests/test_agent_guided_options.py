"""AI 找房结果数量驱动的渐进指引决策测试。"""
from app.services.agentic.guided_search import build_result_guidance
from app.services.agentic.dispatcher import _guided_relaxation_layer


def test_many_results_prompt_missing_decisions_in_priority_order() -> None:
    options = build_result_guidance(
        active_filters={"institution": "UCL"},
        result_count=12,
        relaxation_trace=[],
        attempted_relaxations=[],
    )

    assert [option["kind"] for option in options] == [
        "narrow_room_type", "narrow_budget", "narrow_commute",
    ]


def test_many_results_ask_for_destination_before_commute_limit() -> None:
    options = build_result_guidance(
        active_filters={"room_type": "studio", "price_max": 1800},
        result_count=9,
        relaxation_trace=[],
        attempted_relaxations=[],
    )

    assert options == [{
        "label": "补充学校或目的地",
        "message": "我想补充通勤目的地",
        "filter_patch": None,
        "clear_fields": [],
        "kind": "narrow_destination",
        "icon": "🎓",
    }]


def test_suitable_result_count_does_not_interrupt_user() -> None:
    assert build_result_guidance({}, 6, [], []) == []


def test_few_results_relax_one_layer_at_a_time() -> None:
    filters = {
        "amenities": ["独立卫浴"],
        "poi_requirements": [{"type": "metro", "max_distance_m": 500}],
        "price_max": 1800,
        "room_type": "studio",
    }
    first = build_result_guidance(filters, 2, [], [])
    second = build_result_guidance(filters, 2, [], ["amenities"])
    third = build_result_guidance(filters, 2, [], ["amenities", "poi"])
    fourth = build_result_guidance(filters, 2, [], ["amenities", "poi", "budget"])

    assert first[0]["kind"] == "relax_amenities"
    assert first[0]["clear_fields"] == ["amenities"]
    assert second[0]["kind"] == "relax_poi"
    assert third[0]["kind"] == "relax_budget"
    assert third[0]["filter_patch"] == {"price_max": 2160}
    assert fourth[0]["kind"] == "relax_room_type"
    assert set(fourth[0]["clear_fields"]) == {"property_type", "room_type", "bedrooms"}


def test_relaxation_trace_supplies_verified_count_and_patch() -> None:
    options = build_result_guidance(
        active_filters={"price_max": 2000},
        result_count=1,
        relaxation_trace=[{
            "field": "price_max",
            "action": "预算上限由 2000 调到 2400",
            "before_count": 1,
            "after_count": 5,
            "suggested_filters": {"price_max": 2400},
        }],
        attempted_relaxations=[],
    )

    assert options[0]["label"] == "预算放宽到 2400（约 5 个）"
    assert options[0]["filter_patch"] == {"price_max": 2400}


def test_no_more_relaxation_after_result_count_recovers() -> None:
    options = build_result_guidance(
        active_filters={"price_max": 2400, "room_type": "studio"},
        result_count=5,
        relaxation_trace=[],
        attempted_relaxations=["amenities", "poi", "budget"],
    )

    assert options == []


def test_guided_relaxation_message_maps_to_persisted_layer() -> None:
    assert _guided_relaxation_layer("暂不限制房内设施要求") == "amenities"
    assert _guided_relaxation_layer("暂不限制周边配套要求") == "poi"
    assert _guided_relaxation_layer("把预算上限放宽到 2400") == "budget"
    assert _guided_relaxation_layer("暂不限制户型要求") == "room_type"
    assert _guided_relaxation_layer("我想看看第二套") is None

"""搜索任务边界服务测试 —— 覆盖锚点冲突、显式边界和必要澄清。"""
from __future__ import annotations

import pytest

from app.services.search_task_boundary import (
    NEW_TASK_RESET_FIELDS,
    TaskBoundaryDecision,
    detect_task_boundary,
)


CURRENT_NUS = {
    "country": "SG",
    "city": "Singapore",
    "institution": "NUS",
    "currency": "SGD",
    "price_max": 2400,
    "property_type": "studio",
    "amenities": ["健身房"],
    "_candidate_ids": [11, 12],
}


def test_decision_is_stable_dataclass_api() -> None:
    decision = detect_task_boundary("帮我找 NUS 附近的房子", {})

    assert isinstance(decision, TaskBoundaryDecision)
    assert decision.relation == "continue"
    assert decision.reset_fields == []
    assert decision.clarification_question is None
    assert decision.turn_anchors == {
        "institution": "NUS",
        "country": "SG",
        "city": "Singapore",
    }


def test_no_current_task_is_first_turn_not_new_task() -> None:
    decision = detect_task_boundary("另外帮我看看 UCL 附近", {})

    assert decision.relation == "continue"
    assert decision.turn_anchors["institution"] == "UCL"


@pytest.mark.parametrize(
    "message",
    [
        "另外，我还想看看伦敦的房子",
        "重新找一批预算低一点的",
        "帮朋友看看香港大学附近",
        "给室友看另一批房",
        "顺便也找一下港科大周围的",
        "现有这一单先放着，顺便也替室友看看港大附近",
        "从头开始找吧",
    ],
)
def test_explicit_new_task_phrases_start_new_task(message: str) -> None:
    decision = detect_task_boundary(message, CURRENT_NUS, has_candidates=True)

    assert decision.relation == "new"
    assert set(NEW_TASK_RESET_FIELDS).issubset(decision.reset_fields)
    assert decision.clarification_question is None


@pytest.mark.parametrize(
    ("message", "expected_institution", "expected_country", "expected_city"),
    [
        ("改看看 UCL 周边有什么", "UCL", "GB", "London"),
        ("不是新国大，我想看伦敦政治经济学院附近", "LSE", "GB", "London"),
        ("转而看看香港科技大学周围", "HKUST", "HK", "Hong Kong"),
        ("Maybe show me places around UCLA instead", "UCLA", "US", "Los Angeles"),
        ("想换去 University of Southern California 周边", "USC", "US", "Los Angeles"),
    ],
)
def test_conflicting_school_anchor_starts_new_task(
    message: str,
    expected_institution: str,
    expected_country: str,
    expected_city: str,
) -> None:
    decision = detect_task_boundary(message, CURRENT_NUS)

    assert decision.relation == "new"
    assert decision.turn_anchors == {
        "institution": expected_institution,
        "country": expected_country,
        "city": expected_city,
    }
    assert decision.reset_fields == list(NEW_TASK_RESET_FIELDS)


@pytest.mark.parametrize(
    ("message", "expected_country", "expected_city"),
    [
        ("这回想去 London 看房", "GB", "London"),
        ("How about Hong Kong this time?", "HK", "Hong Kong"),
        ("改看 Los Angeles 的房子", "US", "Los Angeles"),
        ("想看看英国的房源", "GB", None),
    ],
)
def test_conflicting_country_or_city_anchor_starts_new_task(
    message: str,
    expected_country: str,
    expected_city: str | None,
) -> None:
    decision = detect_task_boundary(message, CURRENT_NUS)

    assert decision.relation == "new"
    assert decision.turn_anchors["country"] == expected_country
    if expected_city is not None:
        assert decision.turn_anchors["city"] == expected_city


def test_later_city_anchor_wins_over_earlier_country_in_route_expression() -> None:
    decision = detect_task_boundary(
        "不是要继续留在新加坡，我想换到伦敦找房",
        CURRENT_NUS,
    )

    assert decision.relation == "new"
    assert decision.turn_anchors["country"] == "GB"
    assert decision.turn_anchors["city"] == "London"


def test_same_market_different_school_is_still_new_task() -> None:
    decision = detect_task_boundary("接下来看看 NTU 附近", CURRENT_NUS)

    assert decision.relation == "new"
    assert decision.turn_anchors["country"] == "SG"
    assert decision.turn_anchors["city"] == "Singapore"
    assert decision.turn_anchors["institution"] == "NTU"


@pytest.mark.parametrize(
    ("school_name", "expected"),
    [
        ("National University of Singapore", "NUS"),
        ("Nanyang Technological University", "NTU"),
        ("Singapore Management University", "SMU"),
        ("Singapore University of Technology and Design", "SUTD"),
        ("University College London", "UCL"),
        ("London School of Economics", "LSE"),
        ("King's College London", "KCL"),
        ("Queen Mary University of London", "QMUL"),
        ("University of Hong Kong", "HKU"),
        ("Chinese University of Hong Kong", "CUHK"),
        ("Hong Kong University of Science and Technology", "HKUST"),
        ("University of California, Los Angeles", "UCLA"),
        ("University of Southern California", "USC"),
    ],
)
def test_all_supported_english_school_names_are_deterministic(
    school_name: str,
    expected: str,
) -> None:
    decision = detect_task_boundary(
        f"Please show me homes around {school_name}",
        CURRENT_NUS,
    )

    assert decision.turn_anchors["institution"] == expected


def test_last_school_mention_is_treated_as_target_in_winding_expression() -> None:
    decision = detect_task_boundary(
        "我的意思不是继续看 NUS，也不是只改预算，最后还是想转去 UCL 周边",
        CURRENT_NUS,
    )

    assert decision.relation == "new"
    assert decision.turn_anchors["institution"] == "UCL"


def test_negated_new_task_phrase_keeps_current_search() -> None:
    decision = detect_task_boundary(
        "这不是新任务，还是 NUS，只把预算改成 1750",
        CURRENT_NUS,
        has_candidates=True,
    )

    assert decision.relation == "continue"
    assert decision.reset_fields == []
    assert decision.turn_anchors == {
        "institution": "NUS",
        "country": "SG",
        "city": "Singapore",
    }


def test_additional_budget_clause_is_not_an_independent_task() -> None:
    decision = detect_task_boundary(
        "另外，预算再降到 1800，其他条件都不变",
        CURRENT_NUS,
        has_candidates=True,
    )

    assert decision.relation == "continue"
    assert decision.reset_fields == []


def test_english_us_pronoun_is_not_misread_as_country_anchor() -> None:
    decision = detect_task_boundary(
        "Show UCL options and help us understand the prices",
        CURRENT_NUS,
    )

    assert decision.turn_anchors == {
        "institution": "UCL",
        "country": "GB",
        "city": "London",
    }


def test_retracted_new_target_uses_final_current_target() -> None:
    decision = detect_task_boundary(
        "另外看 UCL……算了，当我没说，继续 NUS",
        CURRENT_NUS,
        has_candidates=True,
    )

    assert decision.relation == "continue"
    assert decision.reset_fields == []
    assert decision.turn_anchors == {
        "institution": "NUS",
        "country": "SG",
        "city": "Singapore",
    }


def test_retracted_new_target_without_replacement_does_not_leak_anchor() -> None:
    decision = detect_task_boundary(
        "另外看 UCL，算了，当我没说",
        CURRENT_NUS,
        has_candidates=True,
    )

    assert decision.relation == "continue"
    assert decision.reset_fields == []
    assert decision.turn_anchors == {}


def test_replacing_rejected_target_clears_all_old_market_state() -> None:
    decision = detect_task_boundary(
        "不要 NUS 了，换 UCL",
        CURRENT_NUS,
        has_candidates=True,
    )

    assert decision.relation == "continue"
    assert decision.turn_anchors == {
        "institution": "UCL",
        "country": "GB",
        "city": "London",
    }
    assert decision.reset_fields == list(NEW_TASK_RESET_FIELDS)
    assert {
        "country",
        "city",
        "institution",
        "currency",
        "price_min",
        "price_max",
        "commute_mode",
        "commute_minutes",
        "_candidate_ids",
        "_compare_ids",
    }.issubset(decision.reset_fields)


@pytest.mark.parametrize(
    "message",
    [
        "取消 NUS，看看 UCL",
        "不看 NUS，改看 UCL",
    ],
)
def test_natural_target_replacement_clears_all_old_market_state(
    message: str,
) -> None:
    decision = detect_task_boundary(
        message,
        CURRENT_NUS,
        has_candidates=True,
    )

    assert decision.relation == "continue"
    assert decision.turn_anchors == {
        "institution": "UCL",
        "country": "GB",
        "city": "London",
    }
    assert decision.reset_fields == list(NEW_TASK_RESET_FIELDS)


@pytest.mark.parametrize(
    "message",
    [
        "把当前搜索从 NUS 改成 UCL",
        "把当前方案由 NUS 换到 UCL",
        "当前搜索改为港大周边",
        "就在原有搜索里转到 London 看看",
        "我不是要另开任务，把当前找房目的地由新加坡调整为伦敦",
        "这次不是另开任务，将现有方案切到香港中文大学附近",
    ],
)
def test_explicit_current_task_mutation_stays_continue_and_resets_dependencies(
    message: str,
) -> None:
    decision = detect_task_boundary(message, CURRENT_NUS, has_candidates=True)

    assert decision.relation == "continue"
    assert "institution" in decision.reset_fields or "city" in decision.reset_fields
    assert "_candidate_ids" in decision.reset_fields
    assert "_compare_ids" in decision.reset_fields
    assert "commute_mode" in decision.reset_fields
    assert "commute_minutes" in decision.reset_fields


def test_structured_turn_anchor_conflict_also_starts_new_task() -> None:
    decision = detect_task_boundary(
        "按这些条件搜索",
        CURRENT_NUS,
        turn_filters={"institution": "香港中文大学"},
    )

    assert decision.relation == "new"
    assert decision.turn_anchors == {
        "institution": "CUHK",
        "country": "HK",
        "city": "Hong Kong",
    }


def test_current_mutation_with_structured_district_conflict_resets_district_state() -> None:
    decision = detect_task_boundary(
        "把当前搜索的区域改成另一个区",
        {**CURRENT_NUS, "district": "West Coast"},
        turn_filters={"district": "Clementi"},
    )

    assert decision.relation == "continue"
    assert decision.turn_anchors["district"] == "clementi"
    assert "district" in decision.reset_fields
    assert "institute_id" in decision.reset_fields
    assert "_candidate_ids" in decision.reset_fields


def test_same_market_school_replacement_clears_old_school_district() -> None:
    decision = detect_task_boundary(
        "把当前搜索从 NUS 改成 NTU",
        {**CURRENT_NUS, "district": "West Coast"},
        has_candidates=True,
    )

    assert decision.relation == "continue"
    assert decision.turn_anchors["institution"] == "NTU"
    assert "district" in decision.reset_fields
    assert "institution" in decision.reset_fields
    assert "_candidate_ids" in decision.reset_fields


@pytest.mark.parametrize(
    "message",
    [
        "预算降到 2000 新币",
        "再便宜一点，但其他都不变",
        "只看 studio，最好带健身房和泳池",
        "不要合租，独立卫浴必须有",
        "取消健身房要求，区域不限",
        "户型改成两居室",
    ],
)
def test_filter_refinements_do_not_start_new_task(message: str) -> None:
    decision = detect_task_boundary(message, CURRENT_NUS, has_candidates=True)

    assert decision.relation == "continue"
    assert decision.reset_fields == []


@pytest.mark.parametrize(
    "message",
    [
        "第一套离 UCL 多远？",
        "刚才那套和第二套比较一下",
        "把这个房源加入候选清单",
        "NUS 和 UCL 哪个通勤更方便，对比一下",
        "UCL 的合同押金一般怎么退？",
        "Compare NUS with UCL and tell me which school is better",
        "What is the deposit policy around UCL?",
        "How far is the first property from UCL?",
    ],
)
def test_reference_compare_and_faq_never_start_new_task(message: str) -> None:
    decision = detect_task_boundary(message, CURRENT_NUS, has_candidates=True)

    assert decision.relation == "continue"
    assert decision.reset_fields == []


@pytest.mark.parametrize(
    ("message", "question_fragment"),
    [
        ("帮我找学校附近便宜一点的", "哪所学校"),
        ("那边还有大一点的吗", "哪个国家、城市或区域"),
        ("这个学校周边有 studio 吗", "哪所学校"),
    ],
)
def test_unresolved_vague_reference_clarifies_only_when_needed(
    message: str,
    question_fragment: str,
) -> None:
    decision = detect_task_boundary(message, {"price_max": 2000})

    assert decision.relation == "clarify"
    assert decision.reset_fields == []
    assert decision.clarification_question is not None
    assert question_fragment in decision.clarification_question


@pytest.mark.parametrize(
    "message",
    [
        "学校附近还有便宜一点的吗",
        "那边有没有大一点的房型",
        "这个学校周边再看看",
    ],
)
def test_vague_reference_with_active_anchor_continues(message: str) -> None:
    decision = detect_task_boundary(message, CURRENT_NUS)

    assert decision.relation == "continue"
    assert decision.clarification_question is None


def test_turn_filter_can_resolve_vague_school_without_clarification() -> None:
    decision = detect_task_boundary(
        "这个学校附近有什么",
        {"price_max": 1800},
        turn_filters={"institution": "QMUL"},
    )

    assert decision.relation == "continue"
    assert decision.clarification_question is None
    assert decision.turn_anchors["institution"] == "QMUL"


def test_mode_new_overrides_no_current_task_and_returns_full_reset() -> None:
    decision = detect_task_boundary("继续找房", {}, mode="new")

    assert decision.relation == "new"
    assert decision.reset_fields == list(NEW_TASK_RESET_FIELDS)


def test_mode_continue_overrides_conflict_and_unresolved_reference() -> None:
    conflicting = detect_task_boundary("换看 UCL", CURRENT_NUS, mode="continue")
    vague = detect_task_boundary("那边还有吗", {}, mode="continue")

    assert conflicting.relation == "continue"
    assert conflicting.reset_fields == list(NEW_TASK_RESET_FIELDS)
    assert vague.relation == "continue"
    assert vague.clarification_question is None


def test_candidates_make_empty_filter_state_an_active_task() -> None:
    decision = detect_task_boundary(
        "重新找一批",
        {"_candidate_ids": [1, 2]},
        has_candidates=True,
    )

    assert decision.relation == "new"


def test_unknown_mode_falls_back_to_auto_rules() -> None:
    decision = detect_task_boundary("看看 UCL 附近", CURRENT_NUS, mode="unexpected")

    assert decision.relation == "new"

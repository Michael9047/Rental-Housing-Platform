"""搜索页 Agent 条件回填规则测试。"""

from types import SimpleNamespace

from app.services.agentic.dispatcher import (
    _build_filter_patch,
    _needs_location_clarification,
    _text_stream_chunks,
)
from app.services.agentic.memory import merge_dialogue_filters
from app.services.agentic.query_understanding import QueryUnderstanding


def test_build_filter_patch_skips_soft_preferences() -> None:
    understanding = QueryUnderstanding(
        extracted_filters={
            "district": "苏州工业园区",
            "price_max": 3000,
            "soft_preferences": ["price"],
        }
    )

    patch = _build_filter_patch(
        understanding,
        {"district": "苏州工业园区", "price_max": 3000},
    )

    assert patch == {"district": "苏州工业园区"}


def test_build_filter_patch_keeps_explicit_hard_filter() -> None:
    understanding = QueryUnderstanding(
        extracted_filters={
            "price_max": 3000,
            "hard_filters": ["price_max"],
            "soft_preferences": ["price"],
        }
    )

    patch = _build_filter_patch(understanding, {"price_max": 3000})

    assert patch == {"price_max": 3000}


def test_build_filter_patch_clears_removed_filter() -> None:
    understanding = QueryUnderstanding(remove_fields=["price_min", "price_max"])

    patch = _build_filter_patch(understanding, {})

    assert patch == {"price_min": None, "price_max": None}


def test_build_filter_patch_reset_clears_search_page_fields() -> None:
    patch = _build_filter_patch(QueryUnderstanding(), {}, reset=True)

    assert patch["district"] is None
    assert patch["amenities"] is None
    assert patch["institution"] is None


def test_natural_language_overrides_search_page_context() -> None:
    merged = merge_dialogue_filters(
        message="预算改成 2500 以内",
        previous={"district": "苏州工业园区", "price_max": 3000},
        memory_filters={},
        extracted={"price_max": 2500},
        request_filters={},
    )

    assert merged["district"] == "苏州工业园区"
    assert merged["price_max"] == 2500


def test_short_lease_patch_is_visible_to_search_page() -> None:
    understanding = QueryUnderstanding(
        extracted_filters={"min_lease_months": 1, "max_lease_months": 3}
    )

    patch = _build_filter_patch(
        understanding,
        {"min_lease_months": 1, "max_lease_months": 3},
    )

    assert patch == {"min_lease_months": 1, "max_lease_months": 3}


def test_first_vague_search_requires_location_but_current_country_does_not() -> None:
    ctx = SimpleNamespace(
        runtime=SimpleNamespace(state=SimpleNamespace(last_search_json={})),
        request_filters={},
        context_filters={},
    )
    understanding = QueryUnderstanding(extracted_filters={})

    assert _needs_location_clarification(ctx, understanding) is True

    ctx.context_filters = {"country": "SG"}
    assert _needs_location_clarification(ctx, understanding) is False


def test_deterministic_workflow_chunks_preserve_full_text() -> None:
    reply = "预订流程第一步。然后签署合同，最后查看订单。"
    chunks = _text_stream_chunks(reply, chunk_size=6)

    assert len(chunks) > 1
    assert "".join(chunks) == reply

"""确定性加权评分单测：可复现、优先级改变名次、缺数据中性化"""
import re
from types import SimpleNamespace

import pytest

from app.services.agentic.shared import (
    build_dimension_analysis,
    guard_price_item_narratives,
    parse_commute_meters,
)
from app.services.agentic.agents.compare_agent import (
    COMPARE_STREAM_SYSTEM_PROMPT,
    CompareAgent,
)
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
        PropertyMetrics(property_id=1, price=2000, area=20, transit_meters=300, currency="CNY"),
        PropertyMetrics(property_id=2, price=4000, area=80, transit_meters=2500, currency="CNY"),
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


def test_safety_priority_increases_real_safety_signal_weight() -> None:
    metrics = [
        PropertyMetrics(property_id=1, price=3000, area=40, safety_score=5.0),
        PropertyMetrics(property_id=2, price=3000, area=40, safety_score=1.0),
    ]
    balanced = compute_scores(metrics, "balanced")
    safety = compute_scores(metrics, "safety")

    assert safety[1]["total"] > safety[2]["total"]
    assert (
        safety[1]["total"] - safety[2]["total"]
        > balanced[1]["total"] - balanced[2]["total"]
    )


def test_mixed_currency_prices_are_neutral_not_ranked() -> None:
    scores = compute_scores([
        PropertyMetrics(property_id=1, price=900, currency="GBP"),
        PropertyMetrics(property_id=2, price=1200, currency="SGD"),
    ])
    assert scores[1]["breakdown"]["price"] == 60
    assert scores[2]["breakdown"]["price"] == 60


def test_same_currency_prices_still_compare_normally() -> None:
    scores = compute_scores([
        PropertyMetrics(property_id=1, price=900, currency="GBP"),
        PropertyMetrics(property_id=2, price=1200, currency="GBP"),
    ])
    assert scores[1]["breakdown"]["price"] == 100
    assert scores[2]["breakdown"]["price"] == 40


def test_missing_currency_prices_are_neutral_not_ranked() -> None:
    scores = compute_scores([
        PropertyMetrics(property_id=1, price=900, currency=None),
        PropertyMetrics(property_id=2, price=1200, currency=None),
    ])
    assert scores[1]["breakdown"]["price"] == 60
    assert scores[2]["breakdown"]["price"] == 60


@pytest.mark.parametrize("currencies", [["GBP", "SGD"], [None, "GBP"], [None, None]])
def test_incomparable_currency_llm_item_claims_remove_relative_price_judgments(
    currencies: list[str | None],
) -> None:
    pros, cons = guard_price_item_narratives(
        ["最便宜", "步行3分钟到地铁", "月租 £900"],
        ["价格偏高", "面积较小"],
        currencies,
    )
    assert pros == ["步行3分钟到地铁", "月租 £900"]
    assert cons == ["面积较小"]


def test_same_currency_llm_item_claims_keep_price_judgments() -> None:
    pros, cons = guard_price_item_narratives(
        ["最便宜"],
        ["价格偏高"],
        ["GBP", "GBP"],
    )
    assert pros == ["最便宜"]
    assert cons == ["价格偏高"]


def _comparison_prop(
    property_id: int,
    *,
    currency: str,
    area_sqm: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=property_id,
        institute_id=property_id,
        institute=SimpleNamespace(name=f"Residence {property_id}", name_cn=None, district="SIP", address="Road"),
        name=f"Unit {property_id}",
        currency=currency,
        base_rent=1000 + property_id * 100,
        deposit_amount=None,
        area_sqm=area_sqm,
        bedrooms=1,
        bathrooms=1,
        amenities=[],
        description="",
        property_type="studio",
    )


def _comparison_scores(*property_ids: int) -> dict[int, dict]:
    return {
        property_id: {
            "total": 60,
            "breakdown": {
                "price": 60,
                "commute": 60,
                "space": 60,
                "rating": 60,
                "safety": 60,
            },
        }
        for property_id in property_ids
    }


def _comparison_extras(*property_ids: int) -> dict[int, dict]:
    return {
        property_id: {
            "commute": None,
            "rating": None,
            "review_count": 0,
            "safety_score": None,
        }
        for property_id in property_ids
    }


def test_mixed_currency_analysis_does_not_claim_cheapest() -> None:
    props = [
        _comparison_prop(1, currency="GBP", area_sqm=20),
        _comparison_prop(2, currency="SGD", area_sqm=30),
    ]
    analysis = build_dimension_analysis(
        props,
        _comparison_scores(1, 2),
        _comparison_extras(1, 2),
        "balanced",
    )
    assert "价格最低" not in analysis
    assert "候选币种缺失或不一致" in analysis


def test_missing_areas_do_not_invent_largest_property() -> None:
    props = [
        _comparison_prop(1, currency="GBP"),
        _comparison_prop(2, currency="GBP"),
    ]
    analysis = build_dimension_analysis(
        props,
        _comparison_scores(1, 2),
        _comparison_extras(1, 2),
        "balanced",
    )
    assert "空间最大" not in analysis
    assert "暂时无法比较空间大小" in analysis


def test_parse_commute_meters_handles_decimal_kilometres_before_metres() -> None:
    assert parse_commute_meters("最近交通站点约1.5km") == 1500
    assert parse_commute_meters("最近交通站点约500m") == 500


@pytest.mark.asyncio
async def test_compare_sse_streams_plain_text_and_keeps_structured_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSE 对比使用纯文本 token，结构化卡片继续由确定性规则生成。"""
    props = [
        _comparison_prop(1, currency="GBP", area_sqm=20),
        _comparison_prop(2, currency="SGD", area_sqm=30),
    ]
    metrics = [
        PropertyMetrics(
            property_id=1,
            price=1100,
            area=20,
            transit_meters=300,
            currency="GBP",
        ),
        PropertyMetrics(
            property_id=2,
            price=1200,
            area=30,
            transit_meters=500,
            currency="SGD",
        ),
    ]
    extras = {
        1: {"commute": "最近交通站点约300m", "rating": 4.5, "review_count": 12, "safety_score": 4.2},
        2: {"commute": "最近交通站点约500m", "rating": None, "review_count": 0, "safety_score": None},
    }
    raw_tokens = [
        "综合来看，Residence 1 更适合通勤优先的选择，",
        "Residence 2 的空间更宽裕。建议先确认每天通勤和居住面积哪个更重要，再结合上方真实数据决定。",
    ]

    class StreamingLlm:
        is_available = True

        def __init__(self) -> None:
            self.complete_json_calls = 0
            self.stream_messages: list[dict[str, str]] = []
            self.stream_kwargs: dict = {}

        async def complete_json(self, *_args, **_kwargs):
            self.complete_json_calls += 1
            raise AssertionError("SSE 对比不得调用 complete_json")

        async def complete_text_stream(self, messages, **kwargs):
            self.stream_messages = messages
            self.stream_kwargs = kwargs
            for token in raw_tokens:
                yield token

    async def fake_gather(_props):
        return metrics, extras

    received_tokens: list[str] = []
    received_statuses: list[tuple[str, str]] = []

    async def token_sink(token: str) -> None:
        received_tokens.append(token)

    async def status_sink(status: str, message: str) -> None:
        received_statuses.append((status, message))

    fake_llm = StreamingLlm()
    agent = CompareAgent()
    agent._llm_service = fake_llm
    monkeypatch.setattr(agent, "_gather_compare_metrics", fake_gather)

    result = await agent._compare_props(
        props,
        "balanced",
        token_sink=token_sink,
        status_sink=status_sink,
    )

    assert received_tokens == raw_tokens
    assert result["dimension_analysis"] == "".join(raw_tokens)
    assert result["_reply_streamed"] is True
    assert [item["property_id"] for item in result["items"]] == [1, 2]
    assert all(item["pros"] for item in result["items"])
    assert received_statuses == [("generating", "正在生成对比解读")]
    assert fake_llm.complete_json_calls == 0
    assert fake_llm.stream_messages[0] == {
        "role": "system",
        "content": COMPARE_STREAM_SYSTEM_PROMPT,
    }
    assert "系统得分" not in fake_llm.stream_messages[1]["content"]
    assert "综合 60" not in fake_llm.stream_messages[1]["content"]
    assert "评价记录: 已审核12条" in fake_llm.stream_messages[1]["content"]
    assert "安全数据: 已登记" in fake_llm.stream_messages[1]["content"]
    assert "4.5" not in fake_llm.stream_messages[1]["content"]
    assert "4.2" not in fake_llm.stream_messages[1]["content"]
    assert fake_llm.stream_kwargs == {"temperature": 0.1, "max_tokens": 260}
    visible_reply = "".join(received_tokens)
    assert "得分" not in visible_reply
    assert not re.search(r"\d+(?:\.\d+)?\s*分", visible_reply)


def test_compare_stream_prompt_is_short_and_hides_internal_scores() -> None:
    compact_prompt = "".join(COMPARE_STREAM_SYSTEM_PROMPT.split())
    assert 80 <= len(compact_prompt) <= 160
    assert "80—160字" in COMPARE_STREAM_SYSTEM_PROMPT
    assert "不得重算、引用或展示综合分、分项分、得分或评分" in COMPARE_STREAM_SYSTEM_PROMPT
    assert "不要复述所有维度" in COMPARE_STREAM_SYSTEM_PROMPT


def test_rule_fallback_summary_hides_scores_but_keeps_internal_ranking() -> None:
    props = [
        _comparison_prop(1, currency="GBP", area_sqm=20),
        _comparison_prop(2, currency="GBP", area_sqm=30),
    ]
    scores = _comparison_scores(1, 2)
    scores[1]["total"] = 88
    scores[1]["breakdown"]["commute"] = 90
    scores[2]["total"] = 72
    result = CompareAgent()._rule_based_compare(
        props,
        scores,
        _comparison_extras(1, 2),
        "commute",
    )

    assert result["items"][0]["score"] == 88
    assert result["items"][0]["score_breakdown"]["commute"] == 90
    assert "Residence 1" in result["dimension_analysis"]
    assert "得分" not in result["dimension_analysis"]
    assert "评分" not in result["dimension_analysis"]
    assert not re.search(r"\d+(?:\.\d+)?\s*分", result["dimension_analysis"])

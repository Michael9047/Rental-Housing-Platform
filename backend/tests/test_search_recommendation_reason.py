"""搜索推荐卡理由的确定性生成测试。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.services.agentic.agents.search_agent import _build_recommendation_reason


def _item(*, currency: str = "SGD") -> dict:
    institute = SimpleNamespace(
        district="West Coast",
        city="Singapore",
        amenities=["WiFi", "泳池"],
    )
    unit_type = SimpleNamespace(
        currency=currency,
        base_rent=Decimal("1850"),
        property_type="studio",
        area_sqm=Decimal("22"),
        bathrooms=1,
        amenities=["独立卫浴"],
        special_offer="",
        min_stay_months=6,
    )
    return {
        "unit_type": unit_type,
        "institute": institute,
        "available_rooms": 3,
    }


def test_reason_prioritizes_verified_matches_and_commute() -> None:
    reason = _build_recommendation_reason(
        _item(),
        {
            "currency": "SGD",
            "price_max": 2000,
            "property_type": "studio",
            "amenities": ["独立卫浴"],
        },
        school_name="NUS",
        commute={
            "walk_min": None,
            "transit_min": 18,
            "source": "lookup_table",
        },
    )

    assert reason == (
        "位于West Coast；月租在预算内；Studio · 22㎡ · 1卫；"
        "所需配套：独立卫浴；到NUS公交约18分钟（估算）；目前3套可租。"
    )


def test_reason_does_not_claim_budget_match_for_different_currency() -> None:
    reason = _build_recommendation_reason(
        _item(currency="GBP"),
        {"currency": "SGD", "price_max": 2000},
    )

    assert "预算内" not in reason
    assert "到NUS" not in reason
    assert "配有独立卫浴、WiFi、泳池" in reason
    assert "目前3套可租" in reason

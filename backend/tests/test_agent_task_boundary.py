"""Agent 找房任务边界端到端测试：覆盖续搜、新任务隔离、澄清与复杂改口。"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.chat import ChatSession
from app.services.agentic.agents.search_agent import SearchAgent

from .test_agent import (
    _create_institute,
    _create_unit_type,
    _register_and_login,
)


async def _create_market_unit(
    session_maker: async_sessionmaker[AsyncSession],
    creator_id: int,
    *,
    institute_name: str,
    unit_name: str,
    country: str,
    city: str,
    district: str,
    currency: str,
    price: str,
    amenities: list[str] | None = None,
) -> int:
    """创建一个市场中唯一可租的测试户型，并返回 UnitType.id。"""
    institute_id = await _create_institute(
        session_maker,
        creator_id,
        name=institute_name,
        country=country,
        city=city,
        district=district,
    )
    _, unit_type_id = await _create_unit_type(
        session_maker,
        creator_id,
        institute_id=institute_id,
        name=unit_name,
        price=price,
        bedrooms=1,
        currency=currency,
        amenities=amenities,
    )
    return unit_type_id


async def _seed_three_markets(
    session_maker: async_sessionmaker[AsyncSession],
    creator_id: int,
    *,
    include_hk: bool = True,
) -> tuple[int, int, int | None]:
    """创建 NUS、UCL、HKU 三个互不重叠的市场候选。"""
    sg_unit = await _create_market_unit(
        session_maker,
        creator_id,
        institute_name="NUS West Coast Lodge",
        unit_name="NUS Studio",
        country="SG",
        city="Singapore",
        district="West Coast",
        currency="SGD",
        price="1600",
        amenities=["独立卫浴"],
    )
    gb_unit = await _create_market_unit(
        session_maker,
        creator_id,
        institute_name="UCL Camden Hall",
        unit_name="UCL Studio",
        country="GB",
        city="London",
        district="Camden",
        currency="GBP",
        price="1400",
        amenities=["健身房"],
    )
    hk_unit = None
    if include_hk:
        hk_unit = await _create_market_unit(
            session_maker,
            creator_id,
            institute_name="HKU Pok Fu Lam House",
            unit_name="HKU Studio",
            country="HK",
            city="Hong Kong",
            district="Pok Fu Lam",
            currency="HKD",
            price="10000",
        )
    return sg_unit, gb_unit, hk_unit


async def _create_agent_session(client: AsyncClient, headers: dict[str, str]) -> int:
    response = await client.post("/api/v1/agent/sessions", headers=headers)
    assert response.status_code == 201, response.text
    return int(response.json()["session_id"])


async def _send(
    client: AsyncClient,
    session_id: int,
    headers: dict[str, str],
    message: str,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": message, **(request or {})},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _boundary(data: dict[str, Any]) -> dict[str, Any]:
    boundary = data.get("task_boundary")
    assert isinstance(boundary, dict), data
    assert boundary.get("task_id"), boundary
    return boundary


def _filters(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("state_summary")
    assert isinstance(summary, dict), data
    filters = summary.get("filters")
    assert isinstance(filters, dict), summary
    return filters


async def _saved_state(
    session_maker: async_sessionmaker[AsyncSession],
    session_id: int,
) -> dict[str, Any]:
    async with session_maker() as session:
        chat_session = await session.get(ChatSession, session_id)
        assert chat_session is not None
        return dict(chat_session.accumulated_filters or {})


async def _start_nus_search(
    client: AsyncClient,
    session_id: int,
    headers: dict[str, str],
) -> dict[str, Any]:
    return await _send(
        client,
        session_id,
        headers,
        "帮我找 NUS 附近的房，预算 2,000 新币以内",
    )


@pytest.mark.asyncio
async def test_repeated_single_requirement_reuses_previous_results_without_search(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, gb_unit, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)

    first = await _send(
        client,
        session_id,
        headers,
        "帮我找 UCL 附近预算 1500 镑以内、一定要健身房的房",
    )

    async def fail_if_searched(_self: SearchAgent, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("重复条件命中后不应再次调用 SearchAgent.search")

    monkeypatch.setattr(SearchAgent, "search", fail_if_searched)
    repeated = await _send(client, session_id, headers, "还是要健身房")

    assert repeated["cache_hit"] is True
    assert repeated["reused_message_id"] is not None
    assert repeated["reply"] == "该条件已包含在当前需求中，搜索条件没有变化，继续显示上一次结果。"
    assert [item["property_id"] for item in repeated["recommendations"]] == [gb_unit]
    assert [item["property_id"] for item in repeated["recommendations"]] == [
        item["property_id"] for item in first["recommendations"]
    ]
    assert _boundary(repeated)["task_id"] == _boundary(first)["task_id"]
    assert _filters(repeated) == _filters(first)


@pytest.mark.asyncio
async def test_repeated_requirement_sse_replays_cards_before_final_result(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, gb_unit, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    await _send(
        client,
        session_id,
        headers,
        "帮我找 UCL 附近预算 1500 镑以内、一定要健身房的房",
    )

    async def fail_if_searched(_self: SearchAgent, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("SSE 重复条件命中后不应再次调用 SearchAgent.search")

    monkeypatch.setattr(SearchAgent, "search", fail_if_searched)
    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "还是要健身房"},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: {")
    ]
    metas = [event["meta"] for event in events if "meta" in event]
    preview_index = next(
        index for index, meta in enumerate(metas)
        if meta.get("event") == "search_results"
    )
    result_index = next(
        index for index, meta in enumerate(metas)
        if meta.get("event") == "result"
    )
    preview = metas[preview_index]
    result = metas[result_index]

    assert response.status_code == 200
    assert preview_index < result_index
    assert preview["cache_hit"] is True
    assert [item["property_id"] for item in preview["recommendations"]] == [gb_unit]
    assert result["cache_hit"] is True
    assert "该条件已包含在当前需求中" in body


@pytest.mark.asyncio
async def test_explicit_refresh_bypasses_duplicate_result_reuse(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    await _send(
        client,
        session_id,
        headers,
        "帮我找 UCL 附近预算 1500 镑以内、一定要健身房的房",
    )

    original_search = SearchAgent.search
    search_calls = 0

    async def count_searches(self: SearchAgent, **kwargs: Any) -> dict[str, Any]:
        nonlocal search_calls
        search_calls += 1
        return await original_search(self, **kwargs)

    monkeypatch.setattr(SearchAgent, "search", count_searches)
    refreshed = await _send(client, session_id, headers, "重新搜索，还是要健身房")

    assert search_calls == 1
    assert refreshed["cache_hit"] is False


@pytest.mark.asyncio
async def test_nus_budget_adjustment_continues_current_task(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)

    first = await _start_nus_search(client, session_id, headers)
    adjusted = await _send(
        client,
        session_id,
        headers,
        "预算改到 1,800 新币以内，继续找房",
    )

    first_boundary = _boundary(first)
    adjusted_boundary = _boundary(adjusted)
    assert first_boundary["relation"] == "continue"
    assert adjusted_boundary["relation"] == "continue"
    assert adjusted_boundary["task_id"] == first_boundary["task_id"]

    filters = _filters(adjusted)
    assert filters["institution"] == "NUS"
    assert filters["country"] == "SG"
    assert filters["city"] == "Singapore"
    assert filters["currency"] == "SGD"
    assert filters["price_max"] == 1800
    assert [item["property_id"] for item in adjusted["recommendations"]] == [sg_unit]


@pytest.mark.asyncio
async def test_nus_to_ucl_starts_new_task_without_sg_pollution(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, gb_unit, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)

    nus = await _start_nus_search(client, session_id, headers)
    ucl = await _send(
        client,
        session_id,
        headers,
        "现在开始新的找房任务：帮我找英国 UCL 附近，预算 1,500 镑以内",
    )

    nus_boundary = _boundary(nus)
    ucl_boundary = _boundary(ucl)
    assert ucl_boundary["relation"] == "new"
    assert ucl_boundary["task_id"] != nus_boundary["task_id"]

    filters = _filters(ucl)
    assert filters["institution"] == "UCL"
    assert filters["country"] == "GB"
    assert filters["city"] == "London"
    assert filters["currency"] == "GBP"
    assert filters["price_max"] == 1500
    assert filters.get("district") != "West Coast"

    result_ids = [item["property_id"] for item in ucl["recommendations"]]
    assert result_ids == [gb_unit]
    assert sg_unit not in result_ids
    assert all(item["property"]["country"] == "GB" for item in ucl["recommendations"])


@pytest.mark.asyncio
async def test_help_friend_find_hku_starts_independent_task(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, gb_unit, hk_unit = await _seed_three_markets(session_maker, user_id)
    assert hk_unit is not None
    session_id = await _create_agent_session(client, headers)

    ucl = await _send(
        client,
        session_id,
        headers,
        "帮我找 UCL 附近预算 1,500 镑以内、一定要健身房的房",
    )
    assert [item["property_id"] for item in ucl["recommendations"]] == [gb_unit]

    friend = await _send(
        client,
        session_id,
        headers,
        "另外帮朋友找香港 HKU 附近，预算 12,000 港币以内",
    )

    ucl_boundary = _boundary(ucl)
    friend_boundary = _boundary(friend)
    assert friend_boundary["relation"] == "new"
    assert friend_boundary["task_id"] != ucl_boundary["task_id"]

    filters = _filters(friend)
    assert filters["institution"] == "HKU"
    assert filters["country"] == "HK"
    assert filters["city"] == "Hong Kong"
    assert filters["currency"] == "HKD"
    assert filters["price_max"] == 12000
    assert filters.get("district") != "Camden"
    assert "amenities" not in filters
    assert [item["property_id"] for item in friend["recommendations"]] == [hk_unit]


@pytest.mark.asyncio
async def test_first_candidate_after_empty_new_task_never_uses_old_candidate(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(
        session_maker,
        user_id,
        include_hk=False,
    )
    session_id = await _create_agent_session(client, headers)

    nus = await _start_nus_search(client, session_id, headers)
    assert [item["property_id"] for item in nus["recommendations"]] == [sg_unit]

    hku = await _send(
        client,
        session_id,
        headers,
        "另外帮朋友找 HKU 附近，这是新的找房任务，预算 12,000 港币以内",
    )
    assert _boundary(hku)["relation"] == "new"
    assert hku["recommendations"] == []

    detail = await _send(
        client,
        session_id,
        headers,
        "这里的第一套在哪个国家？",
    )
    assert _boundary(detail)["task_id"] == _boundary(hku)["task_id"]
    assert detail["recommendations"] == []
    assert "新加坡" not in detail["reply"]
    assert "NUS West Coast Lodge" not in detail["reply"]
    assert "当前找房任务还没有可引用的候选户型" in detail["reply"]


@pytest.mark.asyncio
async def test_multiple_budget_corrections_use_last_amount(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    corrected = await _send(
        client,
        session_id,
        headers,
        "预算先改到 2,000 新币以内，等等，不对，预算最后改到 1,800 新币以内，继续找房",
    )

    assert _boundary(corrected)["relation"] == "continue"
    assert _boundary(corrected)["task_id"] == _boundary(first)["task_id"]
    assert _filters(corrected)["price_max"] == 1800
    assert [item["property_id"] for item in corrected["recommendations"]] == [sg_unit]


@pytest.mark.asyncio
async def test_negated_new_task_phrase_does_not_start_new_task(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    continued = await _send(
        client,
        session_id,
        headers,
        "这不是新任务，还是 NUS，只把预算改到 1,800 新币以内，继续找房",
    )

    assert _boundary(continued)["relation"] == "continue"
    assert _boundary(continued)["task_id"] == _boundary(first)["task_id"]
    assert _filters(continued)["institution"] == "NUS"
    assert _filters(continued)["price_max"] == 1800


@pytest.mark.asyncio
async def test_last_destination_correction_to_ucl_wins(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, gb_unit, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    corrected = await _send(
        client,
        session_id,
        headers,
        "还是 NUS……不对，我最后改口：这是另一项找房任务，改找英国 UCL，预算 1,500 镑以内",
    )

    assert _boundary(corrected)["relation"] == "new"
    assert _boundary(corrected)["task_id"] != _boundary(first)["task_id"]
    assert _filters(corrected)["institution"] == "UCL"
    assert _filters(corrected)["country"] == "GB"
    assert _filters(corrected)["currency"] == "GBP"
    assert _filters(corrected)["price_max"] == 1500
    assert [item["property_id"] for item in corrected["recommendations"]] == [gb_unit]


@pytest.mark.asyncio
async def test_replace_nus_with_ucl_keeps_task_id_but_resets_old_market(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, gb_unit, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    memory = await client.put(
        "/api/v1/agent/memory",
        json={
            "preferences": {
                "country": "SG",
                "city": "Singapore",
                "currency": "SGD",
                "price_max": 2000,
            },
            "replace": True,
        },
        headers=headers,
    )
    assert memory.status_code == 200, memory.text
    first = await _start_nus_search(client, session_id, headers)

    replaced = await _send(
        client,
        session_id,
        headers,
        "不要 NUS 了，换 UCL",
    )

    boundary = _boundary(replaced)
    assert boundary["relation"] == "continue"
    assert boundary["task_id"] == _boundary(first)["task_id"]
    assert {"country", "city", "institution", "currency", "price_max"}.issubset(
        boundary["reset_fields"]
    )

    filters = _filters(replaced)
    assert filters["institution"] == "UCL"
    assert filters["country"] == "GB"
    assert filters["city"] == "London"
    assert filters["currency"] == "GBP"
    assert "price_max" not in filters
    result_ids = [item["property_id"] for item in replaced["recommendations"]]
    assert result_ids == [gb_unit]
    assert sg_unit not in result_ids


@pytest.mark.asyncio
async def test_withdraw_ucl_and_return_to_nus_does_not_create_ghost_task(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    withdrawn = await _send(
        client,
        session_id,
        headers,
        "另外看 UCL……算了，当我没说，最后还是继续 NUS 找房，预算 1,800 新币以内",
    )

    assert _boundary(withdrawn)["relation"] == "continue"
    assert _boundary(withdrawn)["task_id"] == _boundary(first)["task_id"]
    assert _filters(withdrawn)["institution"] == "NUS"
    assert _filters(withdrawn)["country"] == "SG"
    assert _filters(withdrawn)["currency"] == "SGD"
    assert _filters(withdrawn)["price_max"] == 1800
    assert [item["property_id"] for item in withdrawn["recommendations"]] == [sg_unit]


@pytest.mark.asyncio
async def test_withdraw_ucl_without_replacement_keeps_nus_state_clean(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    withdrawn = await _send(
        client,
        session_id,
        headers,
        "另外看 UCL，算了，当我没说",
    )

    assert _boundary(withdrawn)["relation"] == "continue"
    assert _boundary(withdrawn)["task_id"] == _boundary(first)["task_id"]
    assert _filters(withdrawn)["institution"] == "NUS"
    assert _filters(withdrawn)["country"] == "SG"
    assert _filters(withdrawn)["city"] == "Singapore"
    assert _filters(withdrawn)["currency"] == "SGD"
    assert _filters(withdrawn)["price_max"] == 2000

    saved = await _saved_state(session_maker, session_id)
    assert saved["institution"] == "NUS"
    assert saved["country"] == "SG"
    assert saved.get("institution") != "UCL"

    continued = await _send(client, session_id, headers, "继续找房")
    assert _boundary(continued)["task_id"] == _boundary(first)["task_id"]
    assert _filters(continued)["institution"] == "NUS"
    assert [item["property_id"] for item in continued["recommendations"]] == [sg_unit]


@pytest.mark.asyncio
async def test_faq_interruption_does_not_change_active_task(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)
    before = await _saved_state(session_maker, session_id)

    faq = await _send(client, session_id, headers, "押金什么时候能退给我？")
    after = await _saved_state(session_maker, session_id)

    assert faq["intent"] == "faq"
    assert _boundary(faq)["relation"] == "continue"
    assert _boundary(faq)["task_id"] == _boundary(first)["task_id"]
    assert after == before

    continued = await _send(
        client,
        session_id,
        headers,
        "回到找房，预算改到 1,800 新币以内，继续找房",
    )
    assert _boundary(continued)["task_id"] == _boundary(first)["task_id"]
    assert _filters(continued)["institution"] == "NUS"
    assert _filters(continued)["price_max"] == 1800


@pytest.mark.asyncio
async def test_vague_school_uses_existing_nus_task_without_clarification(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    closer = await _send(
        client,
        session_id,
        headers,
        "学校附近再近一点，预算先别动，继续找房",
    )

    assert _boundary(closer)["relation"] == "continue"
    assert _boundary(closer)["task_id"] == _boundary(first)["task_id"]
    assert _boundary(closer)["clarification_question"] is None
    assert _filters(closer)["institution"] == "NUS"
    assert _filters(closer)["price_max"] == 2000


@pytest.mark.asyncio
async def test_vague_school_without_task_requires_clarification(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    session_id = await _create_agent_session(client, headers)

    ambiguous = await _send(
        client,
        session_id,
        headers,
        "学校附近帮我找一套",
    )

    boundary = _boundary(ambiguous)
    assert boundary["relation"] == "clarify"
    assert boundary["task_id"] == "pending"
    assert "哪所学校" in (boundary["clarification_question"] or "")
    assert "哪所学校" in ambiguous["reply"]
    assert ambiguous["recommendations"] == []
    assert "_search_task_id" not in await _saved_state(session_maker, session_id)


@pytest.mark.asyncio
async def test_mixed_language_and_comma_price_continue_nus_task(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    mixed = await _send(
        client,
        session_id,
        headers,
        "same NUS plan，预算最后 1,750 SGD 以内，其他 keep，继续找房",
    )

    assert _boundary(mixed)["relation"] == "continue"
    assert _boundary(mixed)["task_id"] == _boundary(first)["task_id"]
    assert _filters(mixed)["institution"] == "NUS"
    assert _filters(mixed)["currency"] == "SGD"
    assert _filters(mixed)["price_max"] == 1750
    assert [item["property_id"] for item in mixed["recommendations"]] == [sg_unit]


@pytest.mark.asyncio
async def test_mixed_language_symbol_price_without_structured_filters(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    mixed = await _send(
        client,
        session_id,
        headers,
        "same NUS plan，预算 down to S$1,750，其他 keep，继续找房",
    )

    assert _boundary(mixed)["relation"] == "continue"
    assert _boundary(mixed)["task_id"] == _boundary(first)["task_id"]
    assert _filters(mixed)["institution"] == "NUS"
    assert _filters(mixed)["country"] == "SG"
    assert _filters(mixed)["currency"] == "SGD"
    assert _filters(mixed)["price_max"] == 1750
    assert [item["property_id"] for item in mixed["recommendations"]] == [sg_unit]


@pytest.mark.asyncio
async def test_ucl_mentioned_inside_deposit_faq_does_not_start_new_task(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)
    before = await _saved_state(session_maker, session_id)

    faq = await _send(
        client,
        session_id,
        headers,
        "UCL 附近的房，押金怎么退？",
    )
    after = await _saved_state(session_maker, session_id)

    assert faq["intent"] == "faq"
    assert _boundary(faq)["relation"] == "continue"
    assert _boundary(faq)["task_id"] == _boundary(first)["task_id"]
    assert after == before
    assert _filters(faq)["institution"] == "NUS"


@pytest.mark.asyncio
async def test_structured_turn_filters_trigger_boundary_before_general_routing(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, gb_unit, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    structured = await _send(
        client,
        session_id,
        headers,
        "按这些条件处理",
        request={
            "filters": {
                "country": "GB",
                "city": "London",
                "institution": "UCL",
                "currency": "GBP",
                "price_max": 1500,
            },
        },
    )

    assert structured["intent"] == "search"
    assert _boundary(structured)["relation"] == "new"
    assert _boundary(structured)["task_id"] != _boundary(first)["task_id"]
    assert _filters(structured)["country"] == "GB"
    assert _filters(structured)["institution"] == "UCL"
    result_ids = [item["property_id"] for item in structured["recommendations"]]
    assert result_ids == [gb_unit]
    assert sg_unit not in result_ids


@pytest.mark.asyncio
async def test_explicit_compare_ids_cannot_cross_task_boundary(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, gb_unit, _ = await _seed_three_markets(
        session_maker,
        user_id,
        include_hk=False,
    )
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)
    assert [item["property_id"] for item in first["recommendations"]] == [sg_unit]

    hku = await _send(
        client,
        session_id,
        headers,
        "另外帮朋友找 HKU 附近，这是新的找房任务",
    )
    assert hku["recommendations"] == []

    compared = await _send(
        client,
        session_id,
        headers,
        "对比这两个户型",
        request={"compare_property_ids": [sg_unit, gb_unit]},
    )

    assert compared["intent"] == "compare"
    assert _boundary(compared)["task_id"] == _boundary(hku)["task_id"]
    assert compared["recommendations"] == []
    assert "请选择 2-5 个户型" in compared["reply"]
    assert "NUS" not in compared["reply"]


@pytest.mark.asyncio
async def test_natural_compare_refs_cannot_fall_back_to_old_task_cart(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    first_nus_unit, _, _ = await _seed_three_markets(
        session_maker,
        user_id,
        include_hk=False,
    )
    second_nus_unit = await _create_market_unit(
        session_maker,
        user_id,
        institute_name="NUS Clementi House",
        unit_name="NUS Ensuite",
        country="SG",
        city="Singapore",
        district="Clementi",
        currency="SGD",
        price="1700",
        amenities=["独立卫浴"],
    )
    session_id = await _create_agent_session(client, headers)

    nus = await _start_nus_search(client, session_id, headers)
    assert {item["property_id"] for item in nus["recommendations"]} == {
        first_nus_unit,
        second_nus_unit,
    }
    for property_id in (first_nus_unit, second_nus_unit):
        added = await client.post(
            "/api/v1/agent/cart/items",
            json={"property_id": property_id},
            headers=headers,
        )
        assert added.status_code == 200, added.text

    hku = await _send(
        client,
        session_id,
        headers,
        "另外帮朋友找 HKU 附近，这是新的找房任务",
    )
    hku_boundary = _boundary(hku)
    assert hku_boundary["relation"] == "new"
    assert hku_boundary["task_id"] != _boundary(nus)["task_id"]
    assert hku["recommendations"] == []

    compared = await _send(
        client,
        session_id,
        headers,
        "对比第一套和第二套",
    )

    assert compared["intent"] == "compare"
    assert _boundary(compared)["task_id"] == hku_boundary["task_id"]
    assert compared["recommendations"] == []
    assert "请选择 2-5 个户型" in compared["reply"]
    assert "NUS" not in compared["reply"]


@pytest.mark.asyncio
async def test_retracted_clear_and_cart_actions_have_no_side_effects(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    sg_unit, _, _ = await _seed_three_markets(session_maker, user_id)
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    kept = await _send(
        client,
        session_id,
        headers,
        "取消预算，算了，当我没说，继续 NUS 找房",
    )
    assert _boundary(kept)["task_id"] == _boundary(first)["task_id"]
    assert _filters(kept)["price_max"] == 2000
    assert "price_max" not in kept["cleared_filters"]

    corrected = await _send(
        client,
        session_id,
        headers,
        "取消预算，算了，预算还是 1,800 新币以内，继续找房",
    )
    assert _filters(corrected)["price_max"] == 1800
    assert [item["property_id"] for item in corrected["recommendations"]] == [sg_unit]

    retracted_cart = await _send(
        client,
        session_id,
        headers,
        "把第一套加入候选清单，算了，当我没说",
    )
    assert retracted_cart["cart_changed"] is False
    cart = await client.get("/api/v1/agent/cart", headers=headers)
    assert cart.status_code == 200, cart.text
    assert cart.json()["items"] == []


@pytest.mark.asyncio
async def test_concurrent_new_tasks_receive_unique_monotonic_task_ids(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, gb_unit, hk_unit = await _seed_three_markets(session_maker, user_id)
    assert hk_unit is not None
    session_id = await _create_agent_session(client, headers)
    first = await _start_nus_search(client, session_id, headers)

    async def start_new(message: str) -> dict[str, Any]:
        return await _send(
            client,
            session_id,
            headers,
            message,
            request={"task_mode": "new"},
        )

    ucl, hku = await asyncio.gather(
        start_new("新任务：找 UCL 附近预算 1,500 镑以内的房"),
        start_new("新任务：找 HKU 附近预算 12,000 港币以内的房"),
    )

    task_ids = {_boundary(ucl)["task_id"], _boundary(hku)["task_id"]}
    assert len(task_ids) == 2
    assert _boundary(first)["task_id"] not in task_ids
    assert [item["property_id"] for item in ucl["recommendations"]] == [gb_unit]
    assert [item["property_id"] for item in hku["recommendations"]] == [hk_unit]

    final_state = await _saved_state(session_maker, session_id)
    assert final_state["_search_task_id"] in task_ids
    assert final_state["_search_task_seq"] == 3

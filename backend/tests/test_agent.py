from __future__ import annotations

import json
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.routes.agent import _serialize_meta, _update_history_metadata
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.models.institute import Institute, InstituteStatus
from app.models.institute_commute import InstituteCommute
from app.models.poi import InstitutePOI
from app.models.unit_type import PropertyType, UnitType, UnitTypeStatus
from app.models.university import University
from app.services.agentic.dispatcher import (
    ASSISTANT_MESSAGE_ID_KEY,
    _INTERNAL_FILTER_KEYS,
    _persist_exchange,
)
from app.services.property_service import PropertyService


async def _register_and_login(
    client: AsyncClient,
    payload: dict[str, str],
) -> tuple[int, dict[str, str]]:
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["id"]
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": payload["username"],
            "password": payload["password"],
        },
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def _create_institute(
    session_maker: async_sessionmaker[AsyncSession],
    creator_id: int,
    *,
    name: str = "SIP Student Residence",
    district: str = "SIP",
    country: str = "CN",
    city: str = "Suzhou",
    amenities: list[str] | None = None,
) -> int:
    async with session_maker() as session:
        institute = Institute(
            name=name,
            address="88 University Road",
            country=country,
            city=city,
            district=district,
            amenities=amenities or [],
            status=InstituteStatus.active,
            created_by=creator_id,
        )
        session.add(institute)
        await session.commit()
        return institute.id


async def _create_unit_type(
    session_maker: async_sessionmaker[AsyncSession],
    creator_id: int,
    *,
    institute_id: int | None = None,
    institute_name: str = "SIP Student Residence",
    institute_amenities: list[str] | None = None,
    name: str = "Sunny two-bedroom",
    price: str = "5200.00",
    area: str | None = "72.50",
    bedrooms: int = 2,
    bathrooms: int = 1,
    status: UnitTypeStatus = UnitTypeStatus.available,
    amenities: list[str] | None = None,
    currency: str = "CNY",
    has_vacancy: bool = True,
    available_count: int = 1,
    min_stay_months: int = 3,
) -> tuple[int, int]:
    if institute_id is None:
        institute_id = await _create_institute(
            session_maker,
            creator_id,
            name=institute_name,
            amenities=institute_amenities,
        )
    async with session_maker() as session:
        unit_type = UnitType(
            institute_id=institute_id,
            name=name,
            description="Near metro with good natural light.",
            base_rent=Decimal(price),
            area_sqm=Decimal(area) if area is not None else None,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            property_type=PropertyType._2bed.value if bedrooms == 2 else PropertyType.studio.value,
            status=status,
            amenities=amenities or [],
            image_urls=["https://example.test/room.jpg"],
            currency=currency,
            total_count=max(available_count, 1),
            available_count=available_count,
            has_vacancy=has_vacancy,
            min_stay_months=min_stay_months,
        )
        session.add(unit_type)
        await session.commit()
        return institute_id, unit_type.id


@pytest.mark.asyncio
async def test_create_agent_session(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)

    resp = await client.post("/api/v1/agent/sessions", headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["session_id"] > 0
    assert data["cart_id"] > 0
    assert data["title"] == "租房推荐 Agent"


@pytest.mark.asyncio
async def test_agent_session_list_excludes_customer_service_sessions(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    agent_resp = await client.post("/api/v1/agent/sessions", headers=headers)
    agent_id = agent_resp.json()["session_id"]
    async with session_maker() as session:
        session.add(ChatSession(user_id=user_id, title="普通客服"))
        await session.commit()

    resp = await client.get("/api/v1/agent/sessions", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert [item["session_id"] for item in resp.json()["items"]] == [agent_id]


@pytest.mark.asyncio
async def test_agent_search_workspace_can_be_restored_by_search_id(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    created = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = created.json()["session_id"]
    workspace = {
        "search_id": "search-workspace-a",
        "route_query": {"q": "UCL 附近", "search_id": "search-workspace-a"},
        "manual_filters": {"country": "GB", "price_max": 1200},
        "ui_state": {"sort_by": "price_asc", "uni_radius": 5},
    }

    saved = await client.put(
        f"/api/v1/agent/sessions/{session_id}/search-workspace",
        headers=headers,
        json=workspace,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["session_id"] == session_id
    assert saved.json()["workspace"] == workspace

    restored = await client.get(
        "/api/v1/agent/search-workspaces/search-workspace-a",
        headers=headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["session_id"] == session_id
    assert restored.json()["workspace"] == workspace
    assert restored.json()["conversation_filters"] == {}

    sessions = await client.get("/api/v1/agent/sessions", headers=headers)
    item = sessions.json()["items"][0]
    assert item["search_id"] == "search-workspace-a"
    assert item["search_workspace"] == workspace


@pytest.mark.asyncio
async def test_agent_search_workspace_is_private_to_owner(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, owner_headers = await _register_and_login(client, landlord_register_payload)
    created = await client.post("/api/v1/agent/sessions", headers=owner_headers)
    session_id = created.json()["session_id"]
    await client.put(
        f"/api/v1/agent/sessions/{session_id}/search-workspace",
        headers=owner_headers,
        json={
            "search_id": "private-search",
            "route_query": {"q": "伦敦"},
            "manual_filters": {},
            "ui_state": {},
        },
    )
    _, other_headers = await _register_and_login(client, {
        "username": "workspace_other_user",
        "email": "workspace_other@example.com",
        "password": "secure-password",
        "role": "tenant",
    })

    restored = await client.get(
        "/api/v1/agent/search-workspaces/private-search",
        headers=other_headers,
    )
    assert restored.status_code == 404


@pytest.mark.asyncio
async def test_guest_agent_sessions_can_be_claimed_after_login(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    guest_created = await client.post("/api/v1/agent/sessions")
    assert guest_created.status_code == 201, guest_created.text
    guest_data = guest_created.json()
    guest_headers = {"Authorization": f"Bearer {guest_data['guest_token']}"}
    guest_sessions = await client.get("/api/v1/agent/sessions", headers=guest_headers)
    assert guest_sessions.status_code == 200
    assert [item["session_id"] for item in guest_sessions.json()["items"]] == [
        guest_data["session_id"],
    ]

    _, user_headers = await _register_and_login(client, landlord_register_payload)
    claimed = await client.post(
        "/api/v1/agent/claim-guest-sessions",
        headers=user_headers,
        json={"guest_token": guest_data["guest_token"]},
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["claimed_sessions"] == 1

    user_sessions = await client.get("/api/v1/agent/sessions", headers=user_headers)
    assert guest_data["session_id"] in {
        item["session_id"] for item in user_sessions.json()["items"]
    }


@pytest.mark.asyncio
async def test_recommendation_and_history_use_unit_type_id_and_full_card(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    # 先建一个空公寓，使目标 Institute.id 与 UnitType.id 明确不同。
    await _create_institute(session_maker, user_id, name="Dummy Residence")
    institute_id, unit_type_id = await _create_unit_type(
        session_maker,
        user_id,
        name="低价单间",
        price="2500.00",
        bedrooms=1,
    )
    assert institute_id != unit_type_id
    async with session_maker() as session:
        institute = await session.get(Institute, institute_id)
        assert institute is not None
        institute.name_cn = "园区学生公寓"
        session.add(InstitutePOI(
            institute_id=institute_id,
            content="周边设施测试数据",
            poi_data={
                "交通": [{"name": "测试地铁站", "distance": "180m"}],
                "购物": [{"name": "测试超市", "distance": "260m"}],
                "医疗": [{"name": "测试医院", "distance": "1.2km"}],
            },
            reviewed=True,
        ))
        await session.commit()

    session_resp = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = session_resp.json()["session_id"]
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "帮我找预算 3000 以内的房子",
            "filters": {"district": "SIP", "price_max": 3000, "currency": "CNY"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert ASSISTANT_MESSAGE_ID_KEY not in resp.text
    assert data["intent"] == "search"
    assert len(data["recommendations"]) == 1
    rec = data["recommendations"][0]
    assert rec["property_id"] == unit_type_id
    assert rec["property"]["id"] == unit_type_id
    assert rec["property"]["unit_type_id"] == unit_type_id
    assert rec["property"]["name"] == "低价单间"
    assert rec["property"]["base_rent"] == 2500.0
    assert rec["property"]["institute_address"] == "88 University Road"
    assert rec["property"]["has_vacancy"] is True
    assert rec["property"]["available_count"] == 1
    assert rec["property"]["institute_id"] == institute_id
    assert rec["property"]["institute_name"] == "SIP Student Residence"
    assert rec["property"]["title"] == "SIP Student Residence · 低价单间"
    assert rec["poi_distances"] == {
        "metro": 180,
        "bus": 180,
        "market": 260,
        "hospital": 1200,
    }
    assert rec["source_metadata"]["entity"] == "unit_type"

    history = await client.get(
        f"/api/v1/agent/sessions/{session_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200
    assistant = history.json()["items"][-1]
    saved_rec = assistant["metadata"]["recommendations"][0]
    assert saved_rec["property_id"] == unit_type_id
    assert saved_rec["property"]["id"] == unit_type_id
    assert saved_rec["property"]["institute_name"] == "SIP Student Residence"
    assert saved_rec["property"]["image_urls"] == ["https://example.test/room.jpg"]
    assert saved_rec["poi_distances"]["market"] == 260


@pytest.mark.asyncio
async def test_singapore_scope_is_normalized_to_country_and_city(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agentic.agents import search_agent as search_agent_module

    class FakeLlm:
        is_available = True

        async def complete_json(self, *_args, **_kwargs):
            return {
                "district": "新加坡",
                "price_max": 2000,
                "currency": "SGD",
                "property_type": "ensuite",
                "amenities": ["空调", "独立卫浴"],
            }

    class FakePropertyService:
        def __init__(self) -> None:
            self.kwargs: dict = {}

        async def search_unit_types(self, **kwargs):
            self.kwargs = kwargs
            return []

    fake_property_service = FakePropertyService()
    monkeypatch.setattr(search_agent_module, "get_llm_service", lambda: FakeLlm())
    agent = search_agent_module.SearchAgent()
    agent._property_service = fake_property_service

    result = await agent.search(
        "只看新加坡 SG，月租不超过 2000 SGD，户型 ensuite",
    )

    assert fake_property_service.kwargs["country"] == "SG"
    assert fake_property_service.kwargs["city"] == "Singapore"
    assert fake_property_service.kwargs["district"] is None
    assert result["effective_filters"]["currency"] == "SGD"
    assert result["extracted_filters"]["country"] == "SG"
    assert result["normalized_cleared_filters"] == ["district"]


@pytest.mark.asyncio
async def test_search_sse_uses_model_tokens_without_calling_complete_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSE 推荐必须直通模型 token，普通接口仍保留一次性补全。"""
    from types import SimpleNamespace

    from app.services import embedding_service
    from app.services.agentic.agents import search_agent as search_agent_module

    model_tokens = ["第一段原始", " token", "，继续输出。"]

    class FakeLlm:
        is_available = True

        def __init__(self) -> None:
            self.complete_text_calls = 0
            self.complete_text_stream_calls = 0

        async def complete_json(self, *_args, **_kwargs):
            return {
                "district": "SIP",
                "currency": "CNY",
                "institution": "Test University",
            }

        async def complete_text(self, *_args, **_kwargs):
            self.complete_text_calls += 1
            return "普通接口的一次性完整推荐回复，长度足够通过现有校验。"

        async def complete_text_stream(self, *_args, **_kwargs):
            self.complete_text_stream_calls += 1
            for token in model_tokens:
                yield token

    institute = SimpleNamespace(
        id=31,
        name="SIP Student Residence",
        district="SIP",
        city="Suzhou",
        country="CN",
        latitude=Decimal("31.274"),
        longitude=Decimal("120.742"),
        amenities=["健身房"],
        description="Near campus",
    )
    unit_type = SimpleNamespace(
        id=41,
        name="Studio",
        currency="CNY",
        base_rent=Decimal("2600"),
        bedrooms=1,
        bathrooms=1,
        area_sqm=Decimal("28"),
        amenities=["独立卫浴"],
        special_offer="",
    )

    class FakePropertyService:
        async def search_unit_types(self, **_kwargs):
            return [{
                "unit_type": unit_type,
                "institute": institute,
                "available_rooms": 2,
                "embedding": None,
            }]

    async def no_embedding(_self, _text: str):
        return None

    async def fake_lookup_institution(_name: str):
        return {
            "id": 71,
            "name": "Test University",
            "lat": 31.280,
            "lng": 120.750,
            "country": "CN",
            "city": "Suzhou",
        }

    async def timeout_commute_batch(**_kwargs):
        raise TimeoutError

    fake_llm = FakeLlm()
    monkeypatch.setattr(search_agent_module, "get_llm_service", lambda: fake_llm)
    monkeypatch.setattr(embedding_service.EmbeddingService, "generate_embedding", no_embedding)
    from app.services import commute_service
    monkeypatch.setattr(commute_service, "calculate_commute_batch", timeout_commute_batch)
    agent = search_agent_module.SearchAgent()
    agent._property_service = FakePropertyService()
    agent._lookup_institution = fake_lookup_institution

    received_tokens: list[str] = []
    received_statuses: list[tuple[str, str]] = []
    received_previews: list[dict] = []
    event_order: list[str] = []

    async def token_sink(token: str) -> None:
        event_order.append("token")
        received_tokens.append(token)

    async def status_sink(status: str, message: str) -> None:
        event_order.append(f"status:{status}")
        received_statuses.append((status, message))

    async def preview_sink(payload: dict) -> None:
        event_order.append("preview")
        received_previews.append(payload)

    streamed = await agent.search(
        "帮我推荐 SIP 的单间",
        token_sink=token_sink,
        status_sink=status_sink,
        preview_sink=preview_sink,
    )

    assert received_tokens[:len(model_tokens)] == model_tokens
    assert streamed["reply"].startswith("".join(model_tokens))
    assert "找到 1 种户型，先看前 1 个" not in streamed["reply"]
    assert streamed["_reply_streamed"] is True
    assert received_statuses == [("generating", "正在生成推荐回复")]
    assert received_previews[0]["recommendations"][0]["property_id"] == 41
    assert event_order.index("preview") < event_order.index("status:generating")
    assert event_order.index("status:generating") < event_order.index("token")
    assert fake_llm.complete_text_stream_calls == 1
    assert fake_llm.complete_text_calls == 0

    regular = await agent.search("帮我推荐 SIP 的单间")
    assert "普通接口的一次性完整推荐回复" in regular["reply"]
    assert regular["_reply_streamed"] is False
    assert fake_llm.complete_text_calls == 1


@pytest.mark.asyncio
async def test_agent_limits_cards_to_twenty_but_preserves_total(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    institute_id = await _create_institute(session_maker, user_id)
    for index in range(25):
        await _create_unit_type(
            session_maker,
            user_id,
            institute_id=institute_id,
            name=f"测试户型 {index + 1}",
            price=str(2000 + index),
            bedrooms=1,
        )
    session_id = (await client.post(
        "/api/v1/agent/sessions", headers=headers
    )).json()["session_id"]

    response = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我找 SIP 的房子", "filters": {"district": "SIP"}},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["recommendation_total"] == 25
    assert len(data["recommendations"]) == 20
    assert "共 25 种户型" in data["reply"]

    history = await client.get(
        f"/api/v1/agent/sessions/{session_id}/messages", headers=headers
    )
    assistant = history.json()["items"][-1]
    assert assistant["metadata"]["recommendation_total"] == 25
    assert len(assistant["metadata"]["recommendations"]) == 20


@pytest.mark.asyncio
async def test_candidate_reference_follow_up_uses_real_location_and_commute(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    institute_id = await _create_institute(
        session_maker,
        user_id,
        name="West Coast Lodge",
        district="新加坡-西海岸",
        country="SG",
        city="Singapore",
    )
    _, unit_type_id = await _create_unit_type(
        session_maker,
        user_id,
        institute_id=institute_id,
        name="主卧套间",
        price="1445",
        bedrooms=1,
        currency="SGD",
        amenities=["独立卫浴", "空调"],
    )
    async with session_maker() as session:
        university = University(
            name="National University of Singapore",
            name_cn="新加坡国立大学",
            abbreviation="NUS",
            aliases=["nus"],
            city="Singapore",
            country="SG",
            latitude=1.2966,
            longitude=103.7764,
            is_active=True,
        )
        session.add(university)
        await session.flush()
        session.add(InstituteCommute(
            institute_id=institute_id,
            university_id=university.id,
            transit_min=25,
            walk_min=45,
            drive_min=10,
            source="seed",
        ))
        await session.commit()

    session_id = (await client.post(
        "/api/v1/agent/sessions", headers=headers
    )).json()["session_id"]
    searched = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我找新加坡的房子", "filters": {"country": "SG"}},
        headers=headers,
    )
    assert searched.status_code == 200, searched.text
    assert searched.json()["recommendations"][0]["property_id"] == unit_type_id

    follow_up = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "刚才第一个户型在哪个国家？离 NUS 大概多久？"},
        headers=headers,
    )

    assert follow_up.status_code == 200, follow_up.text
    data = follow_up.json()
    assert data["intent"] == "general"
    assert "位于新加坡" in data["reply"]
    assert "公交约 25 分钟" in data["reply"]
    assert "步行约 45 分钟" in data["reply"]
    assert data["recommendations"] == []


@pytest.mark.asyncio
async def test_clear_all_filters_and_view_all_quick_reply_use_search_protocol(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_unit_type(session_maker, user_id, name="全部公寓测试户型")
    session_id = (await client.post(
        "/api/v1/agent/sessions", headers=headers
    )).json()["session_id"]

    await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "帮我找 SIP 预算 3000 的单间",
            "filters": {"district": "SIP", "price_max": 3000, "property_type": "studio"},
        },
        headers=headers,
    )
    cleared = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "清空所有筛选条件"},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    cleared_data = cleared.json()
    assert cleared_data["intent"] == "search"
    assert cleared_data["reply"].startswith("已清空全部筛选条件")
    assert {"country", "district", "price_max", "property_type", "amenities"}.issubset(
        set(cleared_data["cleared_filters"])
    )
    assert cleared_data["state_summary"]["filters"] == {}

    view_all = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "查看全部公寓"},
        headers=headers,
    )
    assert view_all.status_code == 200, view_all.text
    assert view_all.json()["intent"] == "search"
    assert view_all.json()["reply"].startswith("已清空全部筛选条件")


@pytest.mark.asyncio
async def test_agent_recommend_excludes_unavailable(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_unit_type(
        session_maker,
        user_id,
        name="已出租户型",
        status=UnitTypeStatus.rented,
    )
    session_id = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我推荐房子", "filters": {"district": "SIP"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["recommendations"] == []


@pytest.mark.asyncio
async def test_natural_filter_clear_overrides_general_and_suppresses_long_term_memory(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agentic import dispatcher as dispatcher_module

    async def classify_as_general(_message: str, _history: list[dict] | None = None) -> dict:
        return {"intent": "general", "stage": "general"}

    monkeypatch.setattr(dispatcher_module, "classify_message", classify_as_general)
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    memory = await client.put(
        "/api/v1/agent/memory",
        json={
            "preferences": {
                "district": "SIP",
                "price_min": 1200,
                "price_max": 3600,
                "property_type": "studio",
            }
        },
        headers=headers,
    )
    assert memory.status_code == 200, memory.text
    session_id = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]

    cleared = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "取消预算，区域不限，也不要户型限制"},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    data = cleared.json()
    # “区域不限”原本会被兜底分类成 general；清除协议必须将其作为搜索变更执行。
    assert data["intent"] == "search"
    assert data["reply"].startswith("已取消预算、城市/区域、户型限制")
    assert set(data["cleared_filters"]) == {
        "district", "price_min", "price_max", "bedrooms", "property_type", "room_type",
    }
    for field in data["cleared_filters"]:
        assert field not in data["state_summary"]["filters"]

    async with session_maker() as session:
        chat_session = await session.get(ChatSession, session_id)
        assert chat_session is not None
        state = chat_session.accumulated_filters or {}
        for field in data["cleared_filters"]:
            assert field not in state
        assert set(state["_cleared_filters"]) == set(data["cleared_filters"])

    # 下一轮没有重复 clear_fields，长期偏好也不能把已取消条件偷偷带回来。
    follow_up = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "继续找房"},
        headers=headers,
    )
    assert follow_up.status_code == 200, follow_up.text
    assert follow_up.json()["cleared_filters"] == []
    for field in data["cleared_filters"]:
        assert field not in follow_up.json()["state_summary"]["filters"]


@pytest.mark.asyncio
async def test_null_does_not_clear_but_explicit_clear_fields_wins_over_stale_context(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    session_id = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]
    seeded = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "帮我找房",
            "filters": {"district": "Camden", "price_max": 1800},
        },
        headers=headers,
    )
    assert seeded.status_code == 200, seeded.text

    null_only = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "继续找房",
            "context_filters": {"price_max": None},
        },
        headers=headers,
    )
    assert null_only.status_code == 200, null_only.text
    assert null_only.json()["cleared_filters"] == []
    assert null_only.json()["state_summary"]["filters"]["price_max"] == 1800

    explicit = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "继续找房",
            # 即使搜索栏旧快照仍带值，独立 clear_fields 也拥有最高优先级。
            "context_filters": {"district": "Camden", "price_max": 1800},
            "clear_fields": ["price_max"],
        },
        headers=headers,
    )
    assert explicit.status_code == 200, explicit.text
    assert explicit.json()["cleared_filters"] == ["price_max"]
    assert "price_max" not in explicit.json()["state_summary"]["filters"]
    assert explicit.json()["filter_patch"].get("price_max") is None


@pytest.mark.asyncio
async def test_memory_crud_and_user_isolation(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers_a = await _register_and_login(client, landlord_register_payload)
    _, headers_b = await _register_and_login(client, {
        "username": "second_tenant",
        "email": "second_tenant@example.com",
        "password": "secure-password",
        "role": "tenant",
    })

    put = await client.put(
        "/api/v1/agent/memory",
        json={"preferences": {"country": "SG", "price_max": 2800, "amenities": ["健身房"]}},
        headers=headers_a,
    )
    assert put.status_code == 200
    assert put.json()["preferences"]["country"] == "SG"

    own = await client.get("/api/v1/agent/memory", headers=headers_a)
    other = await client.get("/api/v1/agent/memory", headers=headers_b)
    assert own.json()["preferences"]["price_max"] == 2800
    assert other.json()["preferences"] == {}

    deleted = await client.delete("/api/v1/agent/memory", headers=headers_a)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/agent/memory", headers=headers_a)).json()["preferences"] == {}


@pytest.mark.asyncio
async def test_cart_ids_are_unit_type_ids_and_duplicates_are_idempotent(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_institute(session_maker, user_id, name="Dummy Residence")
    institute_id, unit_type_id = await _create_unit_type(session_maker, user_id)
    assert institute_id != unit_type_id

    first = await client.post(
        "/api/v1/agent/cart/items",
        json={"property_id": unit_type_id, "reason": "预算合适"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["property_id"] == unit_type_id
    assert first.json()["property"]["institute_id"] == institute_id

    duplicate = await client.post(
        "/api/v1/agent/cart/items",
        json={"property_id": unit_type_id},
        headers=headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == first.json()["id"]
    assert len((await client.get("/api/v1/agent/cart", headers=headers)).json()["items"]) == 1

    removed = await client.delete(
        f"/api/v1/agent/cart/items/{unit_type_id}", headers=headers
    )
    assert removed.status_code == 204
    assert (await client.get("/api/v1/agent/cart", headers=headers)).json()["items"] == []


@pytest.mark.asyncio
async def test_add_nonexistent_unit_type_to_cart(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    resp = await client.post(
        "/api/v1/agent/cart/items",
        json={"property_id": 9999},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_first_recommendation_uses_candidate_snapshot(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, unit_type_id = await _create_unit_type(
        session_maker, user_id, name="推荐目标户型"
    )
    session_id = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]

    searched = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我找 SIP 的房子", "filters": {"district": "SIP"}},
        headers=headers,
    )
    assert searched.status_code == 200
    assert searched.json()["recommendations"][0]["property_id"] == unit_type_id

    added = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "把第一个加入候选清单"},
        headers=headers,
    )
    assert added.status_code == 200
    assert added.json()["intent"] == "manage_cart"
    assert added.json()["cart_changed"] is True
    items = (await client.get("/api/v1/agent/cart", headers=headers)).json()["items"]
    assert [item["property_id"] for item in items] == [unit_type_id]


@pytest.mark.asyncio
async def test_cart_compare_enforces_two_to_five_and_uses_five_dimensions(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, cheap_id = await _create_unit_type(
        session_maker, user_id, institute_name="Cheap Residence", name="便宜户型", price="2000"
    )
    _, pricey_id = await _create_unit_type(
        session_maker, user_id, institute_name="Premium Residence", name="高价户型", price="9000"
    )

    await client.post("/api/v1/agent/cart/items", json={"property_id": cheap_id}, headers=headers)
    one = await client.post("/api/v1/agent/cart/compare", headers=headers)
    assert one.status_code == 400

    await client.post("/api/v1/agent/cart/items", json={"property_id": pricey_id}, headers=headers)
    compared = await client.post(
        "/api/v1/agent/cart/compare",
        json={"priority": "budget"},
        headers=headers,
    )
    assert compared.status_code == 200, compared.text
    data = compared.json()
    assert data["priority"] == "budget"
    assert len(data["items"]) == 2
    by_id = {item["property_id"]: item for item in data["items"]}
    assert by_id[cheap_id]["score"] > by_id[pricey_id]["score"]
    assert set(by_id[cheap_id]["score_breakdown"]) == {
        "price", "commute", "space", "rating", "safety"
    }


@pytest.mark.asyncio
async def test_independent_compare_session_and_follow_up_persist_priority(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, first_id = await _create_unit_type(
        session_maker, user_id, institute_name="Residence A", name="户型 A", price="2500"
    )
    _, second_id = await _create_unit_type(
        session_maker, user_id, institute_name="Residence B", name="户型 B", price="3200"
    )

    created = await client.post(
        "/api/v1/compare/sessions",
        json={"property_ids": [first_id, second_id], "priority": "balanced"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["property_ids"] == [first_id, second_id]

    follow_up = await client.post(
        f"/api/v1/compare/sessions/{data['id']}/messages",
        json={"message": "安全和治安最重要，请重新比较"},
        headers=headers,
    )
    assert follow_up.status_code == 200, follow_up.text
    assert "安全优先" in follow_up.json()["reply"]

    loaded = await client.get(
        f"/api/v1/compare/sessions/{data['id']}", headers=headers
    )
    assert loaded.status_code == 200
    assert loaded.json()["priority"] == "safety"


@pytest.mark.asyncio
async def test_independent_compare_session_sse_streams_raw_tokens_and_persists(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """独立对比 SSE 按状态、原始 token、完整会话、DONE 的顺序输出。"""
    from app.services import llm_service as llm_service_module

    raw_tokens = [
        "综合来看，Residence A 更适合作为首选，",
        "Residence B 的空间更宽裕。建议结合通勤与面积做最终选择。",
    ]

    class StreamingLlm:
        is_available = True

        def __init__(self) -> None:
            self.complete_json_calls = 0

        async def complete_json(self, *_args, **_kwargs):
            self.complete_json_calls += 1
            raise AssertionError("独立对比 SSE 不得调用 complete_json")

        async def complete_text_stream(self, *_args, **_kwargs):
            for token in raw_tokens:
                yield token

    fake_llm = StreamingLlm()
    monkeypatch.setattr(llm_service_module, "get_llm_service", lambda: fake_llm)

    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, first_id = await _create_unit_type(
        session_maker,
        user_id,
        institute_name="Residence A",
        name="户型 A",
        price="2500",
    )
    _, second_id = await _create_unit_type(
        session_maker,
        user_id,
        institute_name="Residence B",
        name="户型 B",
        price="3200",
    )

    async with client.stream(
        "POST",
        "/api/v1/compare/sessions/stream",
        json={"property_ids": [first_id, second_id], "priority": "balanced"},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    payload_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert payload_lines[-1] == "[DONE]"

    events = [json.loads(payload) for payload in payload_lines[:-1]]
    statuses = [
        event["meta"]["status"]
        for event in events
        if "meta" in event and event["meta"].get("event") == "status"
    ]
    tokens = [event["token"] for event in events if "token" in event]
    result_events = [
        event["meta"]
        for event in events
        if "meta" in event and event["meta"].get("event") == "result"
    ]
    event_kinds = [
        (
            f"status:{event['meta']['status']}"
            if "meta" in event and event["meta"].get("event") == "status"
            else "result"
            if "meta" in event and event["meta"].get("event") == "result"
            else "token"
            if "token" in event
            else "other"
        )
        for event in events
    ]

    assert statuses == ["comparing", "generating"]
    assert tokens == raw_tokens
    assert event_kinds == [
        "status:comparing",
        "status:generating",
        "token",
        "token",
        "result",
    ]
    assert fake_llm.complete_json_calls == 0
    assert len(result_events) == 1

    persisted_session = result_events[0]["session"]
    full_reply = "".join(raw_tokens)
    assert persisted_session["property_ids"] == [first_id, second_id]
    assert persisted_session["result_cache"]["reply"] == full_reply
    messages = sorted(persisted_session["messages"], key=lambda item: item["id"])
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[-1]["content"] == full_reply

    loaded = await client.get(
        f"/api/v1/compare/sessions/{persisted_session['id']}",
        headers=headers,
    )
    assert loaded.status_code == 200
    assert loaded.json()["result_cache"]["reply"] == full_reply
    loaded_messages = sorted(loaded.json()["messages"], key=lambda item: item["id"])
    assert [message["role"] for message in loaded_messages] == ["user", "assistant"]
    assert loaded_messages[-1]["content"] == full_reply


@pytest.mark.asyncio
async def test_embedded_compare_quick_reply_reuses_candidates_and_changes_priority(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, first_id = await _create_unit_type(
        session_maker, user_id, institute_name="Residence A", name="户型 A", price="2000"
    )
    _, second_id = await _create_unit_type(
        session_maker, user_id, institute_name="Residence B", name="户型 B", price="5000"
    )
    for unit_type_id in (first_id, second_id):
        await client.post(
            "/api/v1/agent/cart/items",
            json={"property_id": unit_type_id},
            headers=headers,
        )
    session_id = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]

    initial = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "请对比候选清单"},
        headers=headers,
    )
    assert initial.status_code == 200, initial.text
    assert initial.json()["intent"] == "compare"
    assert "按预算优先重新对比" in initial.json()["quick_replies"]

    reprioritized = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "按预算优先重新对比"},
        headers=headers,
    )
    assert reprioritized.status_code == 200, reprioritized.text
    assert reprioritized.json()["intent"] == "compare"
    assert "预算优先" in reprioritized.json()["reply"]
    assert "_compare_ids" not in reprioritized.json()["state_summary"]["filters"]

    history = await client.get(
        f"/api/v1/agent/sessions/{session_id}/messages", headers=headers
    )
    saved_state = history.json()["items"][-1]["metadata"]["state_summary"]
    assert "_compare_ids" not in saved_state["filters"]


@pytest.mark.asyncio
async def test_independent_compare_followups_use_real_amenities_and_lease_data(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    _, gym_id = await _create_unit_type(
        session_maker,
        user_id,
        institute_name="Gym Residence",
        institute_amenities=["健身房"],
        name="Gym Studio",
        min_stay_months=12,
    )
    _, pool_id = await _create_unit_type(
        session_maker,
        user_id,
        institute_name="Pool Residence",
        institute_amenities=["泳池"],
        name="Pool Studio",
        min_stay_months=3,
    )
    created = await client.post(
        "/api/v1/compare/sessions",
        json={"property_ids": [gym_id, pool_id]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    compare_id = created.json()["id"]

    amenities = await client.post(
        f"/api/v1/compare/sessions/{compare_id}/messages",
        json={"message": "哪个有健身房？"},
        headers=headers,
    )
    assert amenities.status_code == 200, amenities.text
    assert "明确记录有健身房" in amenities.json()["reply"]
    assert "Gym Residence" in amenities.json()["reply"]

    lease = await client.post(
        f"/api/v1/compare/sessions/{compare_id}/messages",
        json={"message": "哪个更适合长期住？"},
        headers=headers,
    )
    assert lease.status_code == 200, lease.text
    assert "最短租期 12 个月" in lease.json()["reply"]
    assert "最短租期 3 个月" in lease.json()["reply"]
    assert "没有最长租期或续租承诺" in lease.json()["reply"]


@pytest.mark.asyncio
async def test_sse_persists_exactly_one_user_assistant_pair(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    session_id = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]

    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "你好"},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])
    assert response.status_code == 200
    assert '"event": "status"' in body
    assert '"event": "result"' in body
    assert ASSISTANT_MESSAGE_ID_KEY not in body
    assert "data: [DONE]" in body

    async with session_maker() as session:
        count = await session.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
        )
    assert count == 2


@pytest.mark.asyncio
async def test_sse_deterministic_search_reply_is_one_frame_with_real_statuses(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无模型时正文一次发送，不再伪装成固定 12 字的 token 流。"""
    from app.services.agentic import dispatcher as dispatcher_module
    from app.services.agentic.agents import search_agent as search_agent_module

    class OfflineLlm:
        is_available = False

    async def classify_as_search(_message: str, _history: list[dict] | None = None) -> dict:
        return {"intent": "search", "stage": "narrow", "refs": []}

    monkeypatch.setattr(dispatcher_module, "classify_message", classify_as_search)
    monkeypatch.setattr(search_agent_module, "get_llm_service", lambda: OfflineLlm())

    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_unit_type(session_maker, user_id, name="流式测试户型")
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "帮我找 SIP 的房子", "filters": {"district": "SIP"}},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: {")
    ]
    statuses = [event["meta"]["status"] for event in events if "meta" in event and event["meta"].get("event") == "status"]
    tokens = [event["token"] for event in events if "token" in event]

    assert response.status_code == 200
    assert statuses == ["understanding", "searching", "generating"]
    assert len(tokens) == 1
    assert "为您找到 1 种户型" in tokens[0]


@pytest.mark.asyncio
async def test_sse_search_forwards_provider_tokens_without_complete_text(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """端到端确认 dispatch_stream 队列没有合并或重新切割模型 token。"""
    from app.services import embedding_service
    from app.services.agentic import dispatcher as dispatcher_module
    from app.services.agentic.agents import search_agent as search_agent_module

    raw_tokens = ["模型原始块一", "｜模型原始块二"]

    class StreamingLlm:
        is_available = True

        def __init__(self) -> None:
            self.complete_text_calls = 0

        async def complete_json(self, *_args, **_kwargs):
            return {"district": "SIP", "currency": "CNY"}

        async def complete_text(self, *_args, **_kwargs):
            self.complete_text_calls += 1
            raise AssertionError("SSE 搜索不得调用 complete_text")

        async def complete_text_stream(self, *_args, **_kwargs):
            for token in raw_tokens:
                yield token

    async def classify_as_search(_message: str, _history: list[dict] | None = None) -> dict:
        return {"intent": "search", "stage": "narrow", "refs": []}

    async def no_embedding(_self, _text: str):
        return None

    fake_llm = StreamingLlm()
    monkeypatch.setattr(dispatcher_module, "classify_message", classify_as_search)
    monkeypatch.setattr(dispatcher_module, "get_llm_service", lambda: fake_llm)
    monkeypatch.setattr(search_agent_module, "get_llm_service", lambda: fake_llm)
    monkeypatch.setattr(embedding_service.EmbeddingService, "generate_embedding", no_embedding)

    user_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_unit_type(session_maker, user_id, name="原始 Token 户型")
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "帮我找 SIP 的房子", "filters": {"district": "SIP"}},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: {")
    ]
    tokens = [event["token"] for event in events if "token" in event]

    assert response.status_code == 200
    assert tokens[:len(raw_tokens)] == raw_tokens
    assert fake_llm.complete_text_calls == 0


@pytest.mark.asyncio
async def test_sse_persists_candidate_snapshot_for_reference_follow_up(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    institute_id = await _create_institute(
        session_maker,
        user_id,
        name="West Coast Lodge",
        district="West Coast",
        country="SG",
        city="Singapore",
    )
    _, unit_type_id = await _create_unit_type(
        session_maker,
        user_id,
        institute_id=institute_id,
        name="主卧套间",
        price="1445",
        bedrooms=1,
        currency="SGD",
        amenities=["独立卫浴", "空调"],
    )
    async with session_maker() as session:
        university = University(
            name="National University of Singapore",
            name_cn="新加坡国立大学",
            abbreviation="NUS",
            aliases=["nus"],
            city="Singapore",
            country="SG",
            latitude=1.2966,
            longitude=103.7764,
            is_active=True,
        )
        session.add(university)
        await session.flush()
        session.add(InstituteCommute(
            institute_id=institute_id,
            university_id=university.id,
            transit_min=25,
            walk_min=45,
            drive_min=10,
            source="seed",
        ))
        await session.commit()

    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]
    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "帮我找新加坡的房子", "filters": {"country": "SG"}},
        headers=headers,
    ) as response:
        search_body = "".join([chunk async for chunk in response.aiter_text()])
    assert response.status_code == 200
    assert '"event": "result"' in search_body

    async with session_maker() as session:
        chat_session = await session.get(ChatSession, session_id)
        assert chat_session is not None
        assert (chat_session.accumulated_filters or {}).get("_candidate_ids") == [
            unit_type_id
        ]

    async with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{session_id}/messages/stream",
        json={"message": "刚才第一个户型在哪个国家？离 NUS 大概多久？"},
        headers=headers,
    ) as response:
        follow_up_body = "".join([chunk async for chunk in response.aiter_text()])
    assert response.status_code == 200
    assert "位于新加坡" in follow_up_body
    assert "公交约 25 分钟" in follow_up_body
    assert "步行约 45 分钟" in follow_up_body
    assert '"intent": "general"' in follow_up_body
    assert '"recommendations": []' in follow_up_body


@pytest.mark.asyncio
async def test_history_metadata_update_targets_persisted_assistant_not_latest(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    async with session_maker() as session:
        chat_session = await session.get(ChatSession, session_id)
        assert chat_session is not None
        first_result = {
            "reply": "第一轮回复",
            "intent": "search",
            "recommendations": [],
            "quick_replies": ["第一轮快捷入口"],
            "links": [],
            "guided_options": [],
            "state_summary": {"stage": "explore", "filters": {}, "chips": []},
            "filter_patch": {},
        }
        first_assistant_id = await _persist_exchange(
            session,
            chat_session,
            "第一轮问题",
            None,
            first_result,
        )

        # 模拟第一轮路由补全 metadata 前，另一个并发请求已经持久化了新回复。
        latest_assistant = ChatMessage(
            session_id=session_id,
            role=ChatMessageRole.assistant,
            content="第二轮回复",
            metadata_={"sentinel": "第二轮不得被覆盖"},
        )
        session.add(latest_assistant)
        await session.commit()
        latest_assistant_id = latest_assistant.id

        serialized = _serialize_meta({
            **first_result,
            ASSISTANT_MESSAGE_ID_KEY: first_assistant_id,
            "sources": [{"label": "第一轮来源", "status": "verified"}],
        })
        assert ASSISTANT_MESSAGE_ID_KEY not in serialized
        assert ASSISTANT_MESSAGE_ID_KEY not in _INTERNAL_FILTER_KEYS
        await _update_history_metadata(
            session,
            session_id,
            first_assistant_id,
            serialized,
        )

    async with session_maker() as session:
        first_assistant = await session.get(ChatMessage, first_assistant_id)
        latest_assistant = await session.get(ChatMessage, latest_assistant_id)
        assert first_assistant is not None
        assert latest_assistant is not None
        assert first_assistant.metadata_["sources"] == [
            {"label": "第一轮来源", "status": "verified"}
        ]
        assert latest_assistant.metadata_ == {"sentinel": "第二轮不得被覆盖"}


@pytest.mark.asyncio
async def test_sqlite_amenities_filter_uses_institute_and_unit_type_union_before_limit(
    session_maker: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, _headers = await _register_and_login(client, landlord_register_payload)
    await _create_unit_type(
        session_maker,
        user_id,
        institute_name="Cheap Nonmatch",
        name="无配套",
        price="1000",
    )
    _, target_id = await _create_unit_type(
        session_maker,
        user_id,
        institute_name="Gym Residence",
        institute_amenities=["健身房"],
        name="带空调户型",
        price="3000",
        amenities=["空调"],
    )

    async with session_maker() as session:
        rows = await PropertyService(session).search_unit_types(
            amenities=["健身房", "空调"],
            limit=1,
        )
    assert [row["unit_type"].id for row in rows] == [target_id]


@pytest.mark.asyncio
async def test_agent_requires_auth(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/agent/sessions")).status_code == 401
    assert (await client.get("/api/v1/agent/cart")).status_code == 401
    assert (await client.post("/api/v1/agent/cart/compare")).status_code == 401

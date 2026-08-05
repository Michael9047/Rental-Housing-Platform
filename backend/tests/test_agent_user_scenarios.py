"""用户原话回归：NUS 多轮指代、设施追问、对比、会话记录与长期记忆。"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.institute import Institute, InstituteStatus
from app.models.property import Property
from app.models.unit_type import UnitType, UnitTypeStatus
from app.models.university import University
from app.schemas.agent import AgentMessageRequest
from app.services.agentic import query_understanding as query_understanding_module
from app.services.agentic.query_understanding import _rule_fallback, understand_query


async def _register_and_login(
    client: AsyncClient,
    payload: dict[str, str],
) -> tuple[int, dict[str, str]]:
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    user_id = int(response.json()["id"])
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": payload["username"],
            "password": payload["password"],
        },
    )
    assert login.status_code == 200, login.text
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _seed_nus_market(
    session_maker: async_sessionmaker[AsyncSession],
    user_id: int,
) -> list[int]:
    """写入八套不重名的新加坡 Studio 和一套美国对照房源。"""
    async with session_maker() as session:
        session.add(University(
            name="National University of Singapore",
            name_cn="新加坡国立大学",
            abbreviation="NUS",
            aliases=["nus"],
            city="Singapore",
            country="SG",
            latitude=Decimal("1.296600"),
            longitude=Decimal("103.776400"),
            is_active=True,
            is_hot=True,
        ))

        institutes = [
            Institute(
                name="NUS Study Residence A",
                address="10 Clementi Road",
                district="Clementi",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.300000"),
                longitude=Decimal("103.780000"),
                amenities=["WiFi", "健身房", "自习室"],
                description="靠近 NUS 的学生公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="NUS Study Residence B",
                address="20 Dover Road",
                district="Dover",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.305000"),
                longitude=Decimal("103.775000"),
                amenities=["WiFi", "自习室"],
                description="安静的 NUS 学生公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="NUS Study Residence C",
                address="30 Queenstown Road",
                district="Queenstown",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.294000"),
                longitude=Decimal("103.790000"),
                amenities=["WiFi", "健身房", "自习室"],
                description="带公共自习室的 NUS 学生公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="Dover Garden Student Lodge",
                address="40 Dover Close East",
                district="Dover",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.304800"),
                longitude=Decimal("103.781600"),
                amenities=["WiFi", "自习室", "花园"],
                description="靠近 NUS 的花园学生公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="Queenstown Scholar Suites",
                address="61 Commonwealth Drive",
                district="Queenstown",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.300900"),
                longitude=Decimal("103.797400"),
                amenities=["WiFi", "健身房", "自习室"],
                description="女皇镇成熟社区内的学生公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="Clementi Riverside Hall",
                address="75 Clementi Road",
                district="Clementi",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.309200"),
                longitude=Decimal("103.770100"),
                amenities=["WiFi", "自习室", "洗衣房"],
                description="靠近 Clementi 生活区的河畔公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="Buona Vista Campus House",
                address="88 North Buona Vista Road",
                district="Buona Vista",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.307500"),
                longitude=Decimal("103.789600"),
                amenities=["WiFi", "健身房", "自习室"],
                description="靠近地铁与科研园区的校园公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="Pasir Panjang Learning Loft",
                address="101 Pasir Panjang Road",
                district="Pasir Panjang",
                city="Singapore",
                country="SG",
                latitude=Decimal("1.291800"),
                longitude=Decimal("103.775800"),
                amenities=["WiFi", "自习室", "共享厨房"],
                description="适合安静学习的学生 Loft 公寓。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
            Institute(
                name="UCLA Control Residence",
                address="1 Westwood Plaza",
                district="Westwood",
                city="Los Angeles",
                country="US",
                latitude=Decimal("34.068900"),
                longitude=Decimal("-118.445200"),
                amenities=["WiFi", "健身房", "自习室"],
                description="用于验证国家隔离的美国房源。",
                status=InstituteStatus.active,
                created_by=user_id,
            ),
        ]
        session.add_all(institutes)
        await session.flush()

        properties: list[Property] = []
        for index, institute in enumerate(institutes, 1):
            unit_type = UnitType(
                institute_id=institute.id,
                name=f"Studio {index}",
                bedrooms=0,
                bathrooms=1,
                hall_count=0,
                area_sqm=Decimal(str(20 + index)),
                base_rent=Decimal(str(1500 + index * 100)),
                currency="SGD" if institute.country == "SG" else "USD",
                amenities=["空调", "自习室"] if institute.country == "SG" else ["自习室"],
                image_urls=[f"https://example.test/studio-{index}.jpg"],
                description=f"{institute.name} 的 Studio 户型。",
                min_stay_months=3,
                status=UnitTypeStatus.available,
            )
            session.add(unit_type)
            await session.flush()
            properties.append(Property(
                landlord_id=user_id,
                unit_type_id=unit_type.id,
                institute_id=institute.id,
                institute_name=institute.name,
                institute_amenities=json.dumps(institute.amenities, ensure_ascii=False),
                title=f"{institute.name} Studio",
                address=institute.address,
                district=institute.district,
                country=institute.country,
                currency=unit_type.currency,
                latitude=institute.latitude,
                longitude=institute.longitude,
                price_monthly=unit_type.base_rent,
                area_sqm=unit_type.area_sqm,
                bedrooms=0,
                bathrooms=1,
                property_type="studio",
                description=unit_type.description,
                status="available",
                min_stay_months=3,
            ))
        session.add_all(properties)
        await session.commit()
        return [int(property_.id) for property_ in properties]


def test_explicit_nus_and_singapore_hints_are_deterministic() -> None:
    nus = _rule_fallback("找 NUS 附近的 Studio", {})
    assert nus.extracted_filters["institution"] == "NUS"
    assert nus.extracted_filters["country"] == "SG"
    assert nus.extracted_filters["room_type"] == "studio"

    singapore = _rule_fallback("找新加坡 studio 的房子", {})
    assert singapore.extracted_filters["country"] == "SG"
    assert "district" not in singapore.extracted_filters

    study = _rule_fallback("我想要边上有自习室", {"institution": "NUS"})
    assert "自习室" in study.extracted_filters["amenities"]

    short_lease = _rule_fallback("在新加坡找一套房子，然后要短租", {})
    assert short_lease.extracted_filters["country"] == "SG"
    assert short_lease.extracted_filters["min_lease_months"] == 1
    assert short_lease.extracted_filters["max_lease_months"] == 3

    price_floor = _rule_fallback("只看 2100 新币以上的房源", {})
    assert price_floor.extracted_filters["price_min"] == 2100
    assert price_floor.extracted_filters["currency"] == "SGD"

    district = _rule_fallback("只看 Queenstown 区域的房源", {})
    assert district.extracted_filters["district"] == "Queenstown"

    country_switch = _rule_fallback(
        "找美国的 Studio",
        {"country": "SG", "institution": "NUS", "district": "Clementi"},
    )
    assert country_switch.extracted_filters["country"] == "US"
    assert set(country_switch.remove_fields) >= {"institution", "district"}


@pytest.mark.asyncio
async def test_short_lease_hint_overrides_llm_omission(monkeypatch) -> None:
    class LeaseOmittingLLM:
        is_available = True

        async def complete_json(self, *_args, **_kwargs):
            return {
                "extracted_filters": {"country": "SG"},
                "remove_fields": [],
                "remove_values": {},
                "rewritten_query": "在新加坡找短租房",
                "query_kind": "exact",
                "explicit_memory_fields": ["country"],
            }

    monkeypatch.setattr(
        query_understanding_module,
        "get_llm_service",
        lambda: LeaseOmittingLLM(),
    )

    understood = await understand_query("在新加坡找一套房子，然后要短租")

    assert understood.extracted_filters["min_lease_months"] == 1
    assert understood.extracted_filters["max_lease_months"] == 3
    assert "max_lease_months" in understood.explicit_memory_fields


@pytest.mark.asyncio
async def test_budget_and_district_hints_override_llm_omission(monkeypatch) -> None:
    class FilterOmittingLLM:
        is_available = True

        async def complete_json(self, *_args, **_kwargs):
            return {
                "extracted_filters": {"country": "SG"},
                "remove_fields": [],
                "remove_values": {},
                "rewritten_query": "在新加坡找房",
                "query_kind": "exact",
                "explicit_memory_fields": ["country"],
            }

    monkeypatch.setattr(
        query_understanding_module,
        "get_llm_service",
        lambda: FilterOmittingLLM(),
    )

    understood = await understand_query(
        "找 NUS 附近的 Studio，只看 Queenstown 区域，预算至少 2100 新币",
    )

    assert understood.extracted_filters["district"] == "Queenstown"
    assert understood.extracted_filters["price_min"] == 2100
    assert understood.extracted_filters["currency"] == "SGD"
    assert set(understood.extracted_filters["hard_filters"]) >= {"district", "price_min"}
    assert {"district", "price_min", "currency"} <= set(understood.explicit_memory_fields)


def test_agent_message_accepts_20000_and_rejects_more() -> None:
    assert len(AgentMessageRequest(message="啊" * 20_000).message) == 20_000
    with pytest.raises(ValidationError):
        AgentMessageRequest(message="啊" * 20_001)


@pytest.mark.asyncio
async def test_nus_followup_facilities_and_compare_use_same_candidates(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    seeded_ids = await _seed_nus_market(session_maker, user_id)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    first = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "找 NUS 附近的 Studio"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    first_data = first.json()
    assert first_data["raw_intent"] == "search"
    assert first_data["filter_patch"]["institution"] == "NUS"
    assert first_data["filter_patch"]["country"] == "SG"
    assert len(first_data["recommendations"]) == 8
    assert {item["property"]["country"] for item in first_data["recommendations"]} == {"SG"}
    recommendation_titles = [
        item["property"]["title"] for item in first_data["recommendations"]
    ]
    assert len(recommendation_titles) == len(set(recommendation_titles))
    first_property_id = int(first_data["recommendations"][0]["property_id"])

    gym = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "你推荐的这个有健身房嘛"},
        headers=headers,
    )
    assert gym.status_code == 200, gym.text
    gym_data = gym.json()
    assert gym_data["raw_intent"] == "reference_detail"
    assert gym_data["reference_resolution"]["resolved_ids"] == [first_property_id]
    assert gym_data["recommendations"][0]["property_id"] == first_property_id
    assert "健身房" in gym_data["reply"]

    nearby_study = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "这个房子附近有自习室吗？"},
        headers=headers,
    )
    assert nearby_study.status_code == 200, nearby_study.text
    nearby_study_data = nearby_study.json()
    assert nearby_study_data["raw_intent"] == "reference_detail"
    assert nearby_study_data["reference_resolution"]["resolved_ids"] == [first_property_id]
    assert nearby_study_data["recommendations"][0]["property_id"] == first_property_id
    assert any(
        phrase in nearby_study_data["reply"]
        for phrase in ("楼内", "公寓配套")
    )
    assert any(
        phrase in nearby_study_data["reply"]
        for phrase in ("楼外附近", "周边数据")
    )

    study = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "我想要边上有自习室"},
        headers=headers,
    )
    assert study.status_code == 200, study.text
    study_data = study.json()
    assert study_data["raw_intent"] == "search"
    assert "自习室" in study_data["state_summary"]["filters"]["amenities"]
    assert len(study_data["recommendations"]) >= 2
    assert all(
        item["property_id"] in seeded_ids[:-1]
        and "自习室" in (item["property"]["amenities"] or [])
        for item in study_data["recommendations"]
    )
    assert any(phrase in study_data["reply"] for phrase in ("楼内", "公寓配套"))
    assert any(phrase in study_data["reply"] for phrase in ("楼外附近", "周边数据"))

    compare = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "这几套哪个好"},
        headers=headers,
    )
    assert compare.status_code == 200, compare.text
    compare_data = compare.json()
    assert compare_data["raw_intent"] == "compare"
    assert len(compare_data["recommendations"]) >= 2
    assert "对比" in compare_data["reply"] or "综合" in compare_data["reply"]
    assert "S$" in compare_data["reply"]
    assert "自习室" in compare_data["reply"]

    history = await client.get(
        f"/api/v1/agent/sessions/{session_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    first_assistant = next(
        item for item in history.json()["items"] if item["role"] == "assistant"
    )
    stored_recommendations = first_assistant["metadata"]["recommendations"]
    assert stored_recommendations[0]["property"]["country"] == "SG"


@pytest.mark.asyncio
async def test_right_panel_agent_interaction_matrix(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    """覆盖右侧 Agent 的宽泛、精确、连续追问、对比、FAQ 与异常输入。"""
    user_id, headers = await _register_and_login(client, landlord_register_payload)
    seeded_ids = await _seed_nus_market(session_maker, user_id)

    async def new_session() -> int:
        response = await client.post("/api/v1/agent/sessions", headers=headers)
        assert response.status_code == 201, response.text
        return int(response.json()["session_id"])

    async def ask(session_id: int, message: str, **payload) -> dict:
        response = await client.post(
            f"/api/v1/agent/sessions/{session_id}/messages",
            json={"message": message, **payload},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    # 1. 条件不完整：不应跨市场随便推荐。
    broad_session = await new_session()
    broad = await ask(broad_session, "我要找房")
    assert broad["recommendations"] == []
    assert "国家、城市" in broad["reply"]
    assert broad["quick_replies"]

    # 2. 搜索页已有筛选条件时，右侧 Agent 应直接沿用上下文检索。
    panel_session = await new_session()
    panel_search = await ask(
        panel_session,
        "帮我推荐几套适合学生的房源",
        context_filters={"country": "SG", "institution": "NUS"},
    )
    assert panel_search["raw_intent"] == "search"
    assert len(panel_search["recommendations"]) == 8
    panel_titles = [item["property"]["title"] for item in panel_search["recommendations"]]
    assert len(panel_titles) == len(set(panel_titles))
    assert len({item["property_id"] for item in panel_search["recommendations"]}) == 8

    # 3. 连续缩窄条件：预算、设施和指代必须延续同一批候选上下文。
    cheaper = await ask(panel_session, "再便宜一点，最好 2000 新币以内")
    assert cheaper["raw_intent"] == "search"
    assert cheaper["state_summary"]["filters"]["price_max"] == 2000
    assert cheaper["recommendations"]
    assert all(
        float(item["property"]["price_monthly"]) <= 2000
        for item in cheaper["recommendations"]
    )

    facility = await ask(panel_session, "还要有自习室")
    assert facility["raw_intent"] == "search"
    assert "自习室" in facility["state_summary"]["filters"]["amenities"]
    assert facility["recommendations"]

    first_id = int(facility["recommendations"][0]["property_id"])
    reference = await ask(panel_session, "第一套有健身房吗？")
    assert reference["raw_intent"] == "reference_detail"
    assert reference["reference_resolution"]["resolved_ids"] == [first_id]
    assert reference["recommendations"][0]["property_id"] == first_id
    assert "健身房" in reference["reply"]

    # 4. 右侧卡片勾选后传入明确 ID，必须只比较所选房源。
    compare_ids = [
        int(item["property_id"])
        for item in panel_search["recommendations"][:3]
    ]
    compared = await ask(
        panel_session,
        "详细比较这些房源并告诉我哪套更适合",
        compare_property_ids=compare_ids,
    )
    assert compared["raw_intent"] == "compare"
    assert {item["property_id"] for item in compared["recommendations"]} == set(compare_ids)
    assert "综合" in compared["reply"] or "对比" in compared["reply"]

    # 5. 对比不足两套时给出明确提示，而不是生成虚假的比较结论。
    short_compare_session = await new_session()
    short_compare = await ask(
        short_compare_session,
        "对比这套房",
        compare_property_ids=[seeded_ids[0]],
    )
    assert short_compare["raw_intent"] == "compare"
    assert short_compare["recommendations"] == []
    assert "至少选择 2 套" in short_compare["reply"]

    # 6. 未知学校、无关问题与 FAQ 都要有稳定边界回复。
    unknown_session = await new_session()
    unknown = await ask(unknown_session, "找 XYZ 附近的 Studio")
    assert unknown["recommendations"] == []
    assert "未能定位学校" in unknown["reply"]

    general_session = await new_session()
    general = await ask(general_session, "今天天气怎么样？")
    assert general["raw_intent"] == "general"
    assert "租房推荐助手" in general["reply"]

    for question, expected_text in (
        ("预订流程", "房东确认"),
        ("合同如何签", "电子合同"),
        ("押金怎么退", "合同约定"),
        ("有哪些费用", "月租金"),
    ):
        faq = await ask(panel_session, question)
        assert faq["raw_intent"] == "faq"
        assert expected_text in faq["reply"]
        assert faq["links"]

    # 7. 最低预算、英文区域和跨市场切换不能被上一轮状态吞掉。
    district_session = await new_session()
    district_result = await ask(
        district_session,
        "找 NUS 附近的 Studio，只看 Queenstown 区域",
    )
    assert len(district_result["recommendations"]) == 2
    assert {
        item["property"]["district"]
        for item in district_result["recommendations"]
    } == {"Queenstown"}

    floor_session = await new_session()
    floor_result = await ask(
        floor_session,
        "找 NUS 附近的 Studio，预算至少 2100 新币",
    )
    assert len(floor_result["recommendations"]) == 3
    assert all(
        float(item["property"]["price_monthly"]) >= 2100
        for item in floor_result["recommendations"]
    )

    switch_session = await new_session()
    await ask(switch_session, "找 NUS 附近的 Studio")
    switched = await ask(switch_session, "找美国的 Studio，预算 3000 美元以内")
    assert len(switched["recommendations"]) == 1
    assert switched["recommendations"][0]["property_id"] == seeded_ids[-1]
    assert switched["state_summary"]["filters"]["country"] == "US"
    assert "institution" not in switched["state_summary"]["filters"]

    # 8. 空输入由 API 拒绝；右侧输入框同样会在前端禁用发送。
    empty = await client.post(
        f"/api/v1/agent/sessions/{panel_session}/messages",
        json={"message": ""},
        headers=headers,
    )
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_agent_history_memory_long_message_and_session_isolation(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    normal_chat = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "客服咨询"},
        headers=headers,
    )
    assert normal_chat.status_code == 201, normal_chat.text
    agent_session = await client.post("/api/v1/agent/sessions", headers=headers)
    assert agent_session.status_code == 201, agent_session.text
    agent_session_id = int(agent_session.json()["session_id"])

    sessions = await client.get("/api/v1/agent/sessions", headers=headers)
    assert sessions.status_code == 200, sessions.text
    assert sessions.json()["total"] == 1
    assert sessions.json()["items"][0]["session_id"] == agent_session_id

    normal_history = await client.get(
        f"/api/v1/agent/sessions/{normal_chat.json()['id']}/messages",
        headers=headers,
    )
    assert normal_history.status_code == 404

    saved = await client.put(
        "/api/v1/agent/memory",
        json={
            "preferences": {
                "country": "SG",
                "institution": "NUS",
                "room_type": "studio",
                "amenities": ["自习室"],
            },
            "replace": True,
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["preferences"]["country"] == "SG"

    faq = await client.post(
        f"/api/v1/agent/sessions/{agent_session_id}/messages",
        json={"message": "押金怎么退"},
        headers=headers,
    )
    assert faq.status_code == 200, faq.text
    assert faq.json()["intent"] == "faq"
    assert faq.json()["links"]

    history = await client.get(
        f"/api/v1/agent/sessions/{agent_session_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert [item["role"] for item in history.json()["items"]] == ["user", "assistant"]
    assert history.json()["items"][1]["metadata"]["quick_replies"]
    assert history.json()["items"][1]["metadata"]["links"]

    accepted = await client.post(
        f"/api/v1/agent/sessions/{agent_session_id}/messages",
        json={"message": "啊" * 20_000},
        headers=headers,
    )
    assert accepted.status_code == 200, accepted.text
    rejected = await client.post(
        f"/api/v1/agent/sessions/{agent_session_id}/messages",
        json={"message": "啊" * 20_001},
        headers=headers,
    )
    assert rejected.status_code == 422

    cleared = await client.delete("/api/v1/agent/memory", headers=headers)
    assert cleared.status_code == 204
    memory = await client.get("/api/v1/agent/memory", headers=headers)
    assert memory.status_code == 200
    assert memory.json()["preferences"] == {}

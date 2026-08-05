"""Agent 基础接口回归测试。"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.institute import Institute, InstituteStatus
from app.api.v1.routes.agent import _strip_recommendation_scores


def test_recommendation_history_hides_internal_scores() -> None:
    cleaned = _strip_recommendation_scores({
        "recommendations": [{
            "property_id": 1,
            "final_score": 88.5,
            "score_breakdown": {"semantic": 90},
            "similarity": 0.92,
            "match_reason": "综合匹配 89 分 · 测试公寓 · 1室",
        }],
        "score_gap": {"confident": True},
        "scores": {"1": {"total": 89}},
        "tool_trail": [{"score": 89, "name": "内部排序"}],
        "reply": "匹配度：92% · 推荐先看测试公寓",
        "old_compare_reply": "综合得分最高的是「测试公寓」（89 分）。",
        "old_ranking": "🥇 测试公寓 — 89 分（价格 90 | 通勤 88）",
    })

    recommendation = cleaned["recommendations"][0]
    assert "final_score" not in recommendation
    assert "score_breakdown" not in recommendation
    assert "similarity" not in recommendation
    assert "score_gap" not in cleaned
    assert "scores" not in cleaned
    assert "score" not in cleaned["tool_trail"][0]
    assert recommendation["match_reason"] == "测试公寓 · 1室"
    assert cleaned["reply"] == "推荐先看测试公寓"
    assert cleaned["old_compare_reply"] == "更建议优先看「测试公寓」。"
    assert cleaned["old_ranking"] == "🥇 测试公寓"


async def _register_and_login(client: AsyncClient, payload: dict[str, str]) -> tuple[int, dict[str, str]]:
    resp = await client.post("/api/v1/auth/register", json=payload)
    user_id = resp.json()["id"]
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": payload["username"],
            "password": payload["password"],
        },
    )
    token = login_resp.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def _create_property(
    client: AsyncClient,
    headers: dict[str, str],
    landlord_id: int,
    session_maker: async_sessionmaker[AsyncSession],
    **overrides,
) -> int:
    async with session_maker() as session:
        institute = Institute(
            name="Agent 测试公寓",
            address="88 University Road",
            district="SIP",
            country="CN",
            status=InstituteStatus.active,
            created_by=landlord_id,
        )
        session.add(institute)
        await session.commit()
        await session.refresh(institute)

    payload = {
        "title": "Sunny two-bedroom apartment",
        "description": "Near metro with good natural light.",
        "address": "88 University Road",
        "district": "SIP",
        "price_monthly": "5200.00",
        "area_sqm": "72.50",
        "bedrooms": 2,
        "bathrooms": 1,
        "property_type": "apartment",
        "status": "available",
        "landlord_id": landlord_id,
        "institute_id": institute.id,
        **overrides,
    }
    resp = await client.post("/api/v1/properties", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_agent_session(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)

    resp = await client.post("/api/v1/agent/sessions", headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    assert "cart_id" in data
    assert data["title"] == "租房推荐 Agent"


@pytest.mark.asyncio
async def test_first_vague_find_house_message_asks_for_location(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)
    created = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "我要找房"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["intent"] == "recommend"
    assert data["recommendations"] == []
    assert "国家、城市" in data["reply"]
    assert data["quick_replies"]


@pytest.mark.asyncio
async def test_agent_recommend_returns_properties(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, session_maker, title="低价单间", price_monthly="2500.00", bedrooms=1)
    await _create_property(client, headers, landlord_id, session_maker, title="高价公寓", price_monthly="8000.00")

    session_resp = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = session_resp.json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "我想找预算3000以内的房子",
            "filters": {"district": "SIP", "price_min": 0, "price_max": 3000},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "recommend"
    assert data["reply"]
    assert len(data["recommendations"]) == 1
    rec = data["recommendations"][0]
    assert rec["property"]["title"] == "低价单间"
    assert rec["property"]["status"] == "available"


@pytest.mark.asyncio
async def test_agent_recommend_excludes_unavailable(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, session_maker, title="已出租房源", status="rented")

    session_resp = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = session_resp.json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我推荐房子", "filters": {"district": "SIP"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["recommendations"] == []


@pytest.mark.asyncio
async def test_add_to_cart_and_duplicate(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    property_id = await _create_property(client, headers, landlord_id, session_maker)

    # 添加成功
    resp = await client.post(
        "/api/v1/agent/cart/items",
        json={"property_id": property_id, "reason": "预算合适"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()
    assert item["property_id"] == property_id
    assert item["reason"] == "预算合适"

    # 重复添加不报错，返回已有项
    resp = await client.post(
        "/api/v1/agent/cart/items",
        json={"property_id": property_id},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == item["id"]

    # 购物车只有一条
    resp = await client.get("/api/v1/agent/cart", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_add_nonexistent_property_to_cart(
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
async def test_remove_from_cart(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    property_id = await _create_property(client, headers, landlord_id, session_maker)

    await client.post(
        "/api/v1/agent/cart/items",
        json={"property_id": property_id},
        headers=headers,
    )

    resp = await client.delete(f"/api/v1/agent/cart/items/{property_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/agent/cart", headers=headers)
    assert resp.json()["items"] == []

    # 再删返回 404
    resp = await client.delete(f"/api/v1/agent/cart/items/{property_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_empty_cart(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    _, headers = await _register_and_login(client, landlord_register_payload)

    resp = await client.post("/api/v1/agent/cart/compare", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_compare_cart_rule_based(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    cheap_id = await _create_property(client, headers, landlord_id, session_maker, title="便宜房", price_monthly="2000.00")
    pricey_id = await _create_property(client, headers, landlord_id, session_maker, title="贵房", price_monthly="9000.00")

    for pid in (cheap_id, pricey_id):
        await client.post("/api/v1/agent/cart/items", json={"property_id": pid}, headers=headers)

    resp = await client.post("/api/v1/agent/cart/compare", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]
    assert data["recommendation"]
    assert len(data["items"]) == 2
    # LLM 未配置时走规则解释，内部排序不应泄露到响应。
    assert data["ai_available"] is False
    assert data["priority"] == "balanced"
    by_id = {it["property_id"]: it for it in data["items"]}
    assert "价格最有优势" in by_id[cheap_id]["pros"]
    assert cheap_id in by_id and pricey_id in by_id
    assert all("score" not in item and "score_breakdown" not in item for item in data["items"])
    assert "分" not in data["recommendation"]


@pytest.mark.asyncio
async def test_agent_add_first_recommendation_via_message(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    property_id = await _create_property(client, headers, landlord_id, session_maker, title="推荐目标房源")

    session_resp = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = session_resp.json()["session_id"]

    # 先推荐
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我找找 SIP 的房子", "filters": {"district": "SIP"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["recommendations"]) == 1

    # 自然语言加购
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "把第一个加入购物车"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "add_to_cart"
    assert data["cart_changed"] is True

    cart_resp = await client.get("/api/v1/agent/cart", headers=headers)
    items = cart_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["property_id"] == property_id


@pytest.mark.asyncio
async def test_agent_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/agent/sessions")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/agent/cart")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/agent/cart/compare")
    assert resp.status_code == 401

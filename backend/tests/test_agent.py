import pytest
from httpx import AsyncClient


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
    **overrides,
) -> int:
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
    # 新会话是占位标题，收到第一条用户消息后会自动改成消息摘要
    assert data["title"] == "新对话"


@pytest.mark.asyncio
async def test_agent_recommend_returns_properties(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, title="低价单间", price_monthly="2500.00", bedrooms=1)
    await _create_property(client, headers, landlord_id, title="高价公寓", price_monthly="8000.00")

    session_resp = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = session_resp.json()["session_id"]

    # 条件给全（区域/预算/户型/类型）→ 无需引导追问，直接出推荐
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "我想找预算3000以内的房子",
            "filters": {
                "district": "SIP",
                "price_min": 0,
                "price_max": 3000,
                "bedrooms": 1,
                "property_type": "apartment",
            },
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
async def test_agent_elicits_missing_conditions_in_one_panel(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    """条件不全时循循善诱：把所有缺失维度一次性摆成多组面板，而不是一个个串行问"""
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, title="低价单间", price_monthly="2500.00", bedrooms=1)

    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    # 只给了区域 → 预算/户型/类型应该一次性摆成三组面板（不会重复问区域，也不会一个个串行问）
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我找房子", "filters": {"district": "SIP"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "elicit"
    assert data["recommendations"] == []
    groups = data["elicit"]["groups"]
    assert [g["field"] for g in groups] == ["price_max", "bedrooms", "property_type"]
    for g in groups:
        assert g["options"]
        assert any(o["value"] == "__any__" for o in g["options"])  # 每组都能选「不限」
    assert data["elicit"]["allow_custom"] is True

    # 面板一次性提交多个维度（前端把每组选中的 option.value 精确打进 slot_answers）
    # → 直接出结果，不再追问
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "预算 3000、2 室、公寓",
            "slot_answers": {"price_max": "3000", "bedrooms": "2", "property_type": "apartment"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "recommend"
    assert data["elicit"] is None


@pytest.mark.asyncio
async def test_agent_panel_partial_submit_reasks_only_remaining_fields(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    """面板只勾了部分维度也能提交；下一轮只再问还没填的那几个维度"""
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, title="低价单间", price_monthly="2500.00", bedrooms=1)

    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我找房子", "filters": {"district": "SIP"}},
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "预算 3000", "slot_answers": {"price_max": "3000"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "elicit"
    assert [g["field"] for g in data["elicit"]["groups"]] == ["bedrooms", "property_type"]

    # 用「不限」哨兵值一次交完剩下两个维度 → 出结果
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "户型不限、类型不限", "slot_answers": {"bedrooms": "__any__", "property_type": "__any__"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "recommend"
    assert data["elicit"] is None


@pytest.mark.asyncio
async def test_agent_skip_elicit_goes_straight_to_results(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    """用户说「直接推荐」→ 剩余条件按不限处理，立刻出结果，不再追问"""
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, title="低价单间", price_monthly="2500.00", bedrooms=1)

    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "直接推荐吧", "filters": {"district": "SIP"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "recommend"
    assert data["elicit"] is None
    assert len(data["recommendations"]) >= 1


@pytest.mark.asyncio
async def test_agent_recommend_excludes_unavailable(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, title="已出租房源", status="rented")

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
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    property_id = await _create_property(client, headers, landlord_id)

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
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    property_id = await _create_property(client, headers, landlord_id)

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
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    cheap_id = await _create_property(client, headers, landlord_id, title="便宜房", price_monthly="2000.00")
    pricey_id = await _create_property(client, headers, landlord_id, title="贵房", price_monthly="9000.00")

    for pid in (cheap_id, pricey_id):
        await client.post("/api/v1/agent/cart/items", json={"property_id": pid}, headers=headers)

    resp = await client.post("/api/v1/agent/cart/compare", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]
    assert data["recommendation"]
    assert len(data["items"]) == 2
    # LLM 未配置时走规则解释，但得分来自确定性加权公式
    assert data["ai_available"] is False
    assert data["priority"] == "balanced"
    by_id = {it["property_id"]: it for it in data["items"]}
    assert "价格最有优势" in by_id[cheap_id]["pros"]
    assert by_id[cheap_id]["score"] > by_id[pricey_id]["score"]
    assert set(by_id[cheap_id]["score_breakdown"].keys()) == {"price", "commute", "space", "rating"}


@pytest.mark.asyncio
async def test_agent_add_first_recommendation_via_message(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    property_id = await _create_property(client, headers, landlord_id, title="推荐目标房源")

    session_resp = await client.post("/api/v1/agent/sessions", headers=headers)
    session_id = session_resp.json()["session_id"]

    # 先推荐（条件给全，跳过引导追问）
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "message": "帮我找找 SIP 的房子",
            "filters": {
                "district": "SIP",
                "price_max": 9999,
                "bedrooms": 2,
                "property_type": "apartment",
            },
        },
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


@pytest.mark.asyncio
async def test_agent_sessions_list_history_and_delete(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    """多会话：列表、历史回放（推荐卡还原真实房源）、删除"""
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, title="历史房源", price_monthly="2500.00")

    s1 = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]
    s2 = (await client.post("/api/v1/agent/sessions", headers=headers)).json()["session_id"]

    # 在 s1 里聊出一条推荐
    await client.post(
        f"/api/v1/agent/sessions/{s1}/messages",
        json={
            "message": "找个 SIP 的房子",
            "filters": {
                "district": "SIP",
                "price_max": 9999,
                "bedrooms": 2,
                "property_type": "apartment",
            },
        },
        headers=headers,
    )

    # 列表：两个会话都在，s1 标题被首条消息自动命名
    resp = await client.get("/api/v1/agent/sessions", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()
    assert {s["id"] for s in sessions} == {s1, s2}
    s1_row = next(s for s in sessions if s["id"] == s1)
    assert s1_row["title"] == "找个 SIP 的房子"

    # 历史回放：推荐卡带回完整房源对象
    resp = await client.get(f"/api/v1/agent/sessions/{s1}/messages", headers=headers)
    assert resp.status_code == 200
    msgs = resp.json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    recs = msgs[1]["recommendations"]
    assert len(recs) == 1
    assert recs[0]["property"]["title"] == "历史房源"

    # 删除
    assert (await client.delete(f"/api/v1/agent/sessions/{s2}", headers=headers)).status_code == 204
    remaining = (await client.get("/api/v1/agent/sessions", headers=headers)).json()
    assert {s["id"] for s in remaining} == {s1}


@pytest.mark.asyncio
async def test_agent_message_feedback_set_and_clear(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    """点赞/点踩：写入后历史回放能带回来；传 null 取消；不能碰别人的消息"""
    landlord_id, headers = await _register_and_login(client, landlord_register_payload)
    await _create_property(client, headers, landlord_id, title="低价单间", price_monthly="2500.00")

    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]
    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "帮我找房子", "filters": {"district": "SIP", "price_max": 9999}},
        headers=headers,
    )
    data = resp.json()
    message_id = data["message_id"]
    assert message_id is not None

    # 点赞
    resp = await client.patch(
        f"/api/v1/agent/messages/{message_id}/feedback",
        json={"feedback": "up"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"message_id": message_id, "feedback": "up"}

    # 历史回放能看到这条反馈
    resp = await client.get(f"/api/v1/agent/sessions/{session_id}/messages", headers=headers)
    assistant_msg = next(m for m in resp.json() if m["id"] == message_id)
    assert assistant_msg["feedback"] == "up"

    # 再传 null 取消
    resp = await client.patch(
        f"/api/v1/agent/messages/{message_id}/feedback",
        json={"feedback": None},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["feedback"] is None

    # 另一个用户碰不到这条消息
    other_id, other_headers = await _register_and_login(
        client,
        {
            "username": "other_tenant",
            "email": "other_tenant@example.com",
            "password": "Passw0rd!123",
            "role": "tenant",
        },
    )
    resp = await client.patch(
        f"/api/v1/agent/messages/{message_id}/feedback",
        json={"feedback": "down"},
        headers=other_headers,
    )
    assert resp.status_code == 404

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_chat_session(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    # Register & login
    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create session
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "测试对话"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "测试对话"
    assert data["status"] == "active"
    assert "session_id" in data
    assert "id" in data


@pytest.mark.asyncio
async def test_list_chat_sessions(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    # Register & login
    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a few sessions
    await client.post("/api/v1/chat/sessions", json={"title": "对话1"}, headers=headers)
    await client.post("/api/v1/chat/sessions", json={"title": "对话2"}, headers=headers)

    # List sessions
    resp = await client.get("/api/v1/chat/sessions", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 2
    assert sessions[0]["title"] in ("对话1", "对话2")


@pytest.mark.asyncio
async def test_get_messages_empty(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    # Register & login
    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create session
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "空对话"},
        headers=headers,
    )
    session_id = resp.json()["id"]

    # Get messages (empty)
    resp = await client.get(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_delete_chat_session(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    # Register & login
    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create session
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "待删除"},
        headers=headers,
    )
    session_id = resp.json()["id"]

    # Delete session
    resp = await client.delete(
        f"/api/v1/chat/sessions/{session_id}",
        headers=headers,
    )
    assert resp.status_code == 204

    # Verify deletion
    resp = await client.get("/api/v1/chat/sessions", headers=headers)
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_create_session_without_title(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    # Register & login
    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create session without title
    resp = await client.post("/api/v1/chat/sessions", json={}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] is None
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient) -> None:
    # All chat endpoints require auth
    resp = await client.post("/api/v1/chat/sessions", json={"title": "test"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/chat/sessions")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/chat/sessions/1/messages")
    assert resp.status_code == 401

    resp = await client.delete("/api/v1/chat/sessions/1")
    assert resp.status_code == 401

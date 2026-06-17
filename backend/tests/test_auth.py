import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    response = await client.post("/api/v1/auth/register", json=landlord_register_payload)

    assert response.status_code == 201
    created = response.json()
    assert created["username"] == landlord_register_payload["username"]
    assert created["email"] == landlord_register_payload["email"]
    assert created["role"] == "landlord"
    assert "password" not in created
    assert "password_hash" not in created


@pytest.mark.asyncio
async def test_login_success(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    await client.post("/api/v1/auth/register", json=landlord_register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["email"],
            "password": landlord_register_payload["password"],
        },
    )

    assert response.status_code == 200
    token = response.json()
    assert token["access_token"]
    assert token["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure_with_wrong_password(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    await client.post("/api/v1/auth/register", json=landlord_register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_returns_current_user(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json=landlord_register_payload,
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == register_response.json()["id"]

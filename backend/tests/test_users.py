import pytest
from httpx import AsyncClient


async def register_and_login(
    client: AsyncClient,
    payload: dict[str, str],
) -> tuple[dict[str, str | int], dict[str, str]]:
    register_response = await client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": payload["username"],
            "password": payload["password"],
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return register_response.json(), {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_get_update_delete_user(
    client: AsyncClient,
    landlord_payload: dict[str, str],
) -> None:
    _, admin_headers = await register_and_login(
        client,
        {
            "username": "admin_crud",
            "email": "admin_crud@example.com",
            "password": "secure-password",
            "role": "admin",
        },
    )

    create_response = await client.post("/api/v1/users", json=landlord_payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["username"] == "landlord_demo"
    assert created["role"] == "landlord"
    assert "password_hash" not in created

    user_id = created["id"]
    get_response = await client.get(
        f"/api/v1/users/{user_id}",
        headers=admin_headers,
    )
    assert get_response.status_code == 200

    update_response = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"phone": "+8613800000000"},
        headers=admin_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["phone"] == "+8613800000000"

    delete_response = await client.delete(
        f"/api/v1/users/{user_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 204

    missing_response = await client.get(
        f"/api/v1/users/{user_id}",
        headers=admin_headers,
    )
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_list_users(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tenant_cannot_list_users(client: AsyncClient) -> None:
    _, tenant_headers = await register_and_login(
        client,
        {
            "username": "tenant_list",
            "email": "tenant_list@example.com",
            "password": "secure-password",
            "role": "tenant",
        },
    )

    response = await client.get("/api/v1/users", headers=tenant_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_users(client: AsyncClient) -> None:
    admin, admin_headers = await register_and_login(
        client,
        {
            "username": "admin_list",
            "email": "admin_list@example.com",
            "password": "secure-password",
            "role": "admin",
        },
    )

    response = await client.get("/api/v1/users", headers=admin_headers)

    assert response.status_code == 200
    users = response.json()
    assert any(user["id"] == admin["id"] for user in users)
    assert all("password_hash" not in user for user in users)


@pytest.mark.asyncio
async def test_authenticated_user_can_get_own_profile(client: AsyncClient) -> None:
    user, headers = await register_and_login(
        client,
        {
            "username": "tenant_profile",
            "email": "tenant_profile@example.com",
            "password": "secure-password",
            "role": "tenant",
        },
    )

    response = await client.get("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    profile = response.json()
    assert profile["id"] == user["id"]
    assert profile["username"] == user["username"]
    assert "password_hash" not in profile


@pytest.mark.asyncio
async def test_authenticated_user_can_update_own_profile(client: AsyncClient) -> None:
    user, headers = await register_and_login(
        client,
        {
            "username": "tenant_update",
            "email": "tenant_update@example.com",
            "password": "secure-password",
            "role": "tenant",
        },
    )

    response = await client.patch(
        "/api/v1/users/me",
        json={
            "username": "tenant_updated",
            "phone": "+8613900000000",
            "email": "tenant_updated@example.com",
        },
        headers=headers,
    )

    assert response.status_code == 200
    profile = response.json()
    assert profile["id"] == user["id"]
    assert profile["username"] == "tenant_updated"
    assert profile["phone"] == "+8613900000000"
    assert profile["email"] == "tenant_updated@example.com"
    assert profile["role"] == "tenant"
    assert profile["status"] == "active"
    assert "password_hash" not in profile


@pytest.mark.asyncio
async def test_users_me_cannot_change_role_or_status(client: AsyncClient) -> None:
    _, headers = await register_and_login(
        client,
        {
            "username": "tenant_role_guard",
            "email": "tenant_role_guard@example.com",
            "password": "secure-password",
            "role": "tenant",
        },
    )

    response = await client.patch(
        "/api/v1/users/me",
        json={"role": "admin", "status": "disabled"},
        headers=headers,
    )
    profile_response = await client.get("/api/v1/users/me", headers=headers)

    assert response.status_code == 422
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["role"] == "tenant"
    assert profile["status"] == "active"


@pytest.mark.asyncio
async def test_admin_can_update_another_users_role_and_status(client: AsyncClient) -> None:
    target, _ = await register_and_login(
        client,
        {
            "username": "tenant_promote",
            "email": "tenant_promote@example.com",
            "password": "secure-password",
            "role": "tenant",
        },
    )
    _, admin_headers = await register_and_login(
        client,
        {
            "username": "admin_promote",
            "email": "admin_promote@example.com",
            "password": "secure-password",
            "role": "admin",
        },
    )

    response = await client.patch(
        f"/api/v1/users/{target['id']}",
        json={"role": "landlord", "status": "disabled"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == target["id"]
    assert updated["role"] == "landlord"
    assert updated["status"] == "disabled"
    assert "password_hash" not in updated

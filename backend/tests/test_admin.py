import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_stats_requires_admin(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:

    resp = await client.get("/api/v1/admin/stats")
    assert resp.status_code == 401

    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_as_admin(
    client: AsyncClient,
) -> None:

    admin_payload = {
        "username": "admin_user",
        "email": "admin@example.com",
        "password": "admin-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin_user", "password": "admin-pass"},
    )
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_properties" in data


@pytest.mark.asyncio
async def test_admin_moderate_property(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:

    admin_payload = {
        "username": "mod_admin",
        "email": "mod_admin@example.com",
        "password": "mod-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "mod_admin", "password": "mod-pass"},
    )
    admin_token = admin_login.json()["access_token"]

    landlord_resp = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    landlord_id = landlord_resp.json()["id"]
    landlord_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    landlord_token = landlord_login.json()["access_token"]

    create_resp = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    property_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/admin/properties/{property_id}/status",
        params={"new_status": "offline"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    resp = await client.patch(
        f"/api/v1/admin/properties/{property_id}/status",
        params={"new_status": "invalid"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_update_user_role(
    client: AsyncClient,
) -> None:

    admin_payload = {
        "username": "role_admin",
        "email": "role_admin@example.com",
        "password": "role-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "role_admin", "password": "role-pass"},
    )
    admin_token = admin_login.json()["access_token"]

    tenant_payload = {
        "username": "role_target",
        "email": "role_target@example.com",
        "password": "target-pass",
        "role": "tenant",
    }
    tenant_resp = await client.post("/api/v1/auth/register", json=tenant_payload)
    tenant_id = tenant_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/admin/users/{tenant_id}/role",
        params={"new_role": "landlord"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "landlord"


@pytest.mark.asyncio
async def test_admin_audit_logs(
    client: AsyncClient,
) -> None:

    admin_payload = {
        "username": "log_admin",
        "email": "log_admin@example.com",
        "password": "log-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "log_admin", "password": "log-pass"},
    )
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/admin/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_embedding_stats(
    client: AsyncClient,
) -> None:

    admin_payload = {
        "username": "emb_admin",
        "email": "emb_admin@example.com",
        "password": "emb-pass",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "emb_admin", "password": "emb-pass"},
    )
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/admin/embeddings/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "completed" in data
    assert "failed" in data
    assert "pending" in data

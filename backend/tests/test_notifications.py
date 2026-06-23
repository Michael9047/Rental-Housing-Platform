import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_notifications_created_on_booking(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:

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

    tenant_payload = {
        "username": "notif_tenant",
        "email": "notif_tenant@example.com",
        "password": "notif-pass",
        "role": "tenant",
    }
    await client.post("/api/v1/auth/register", json=tenant_payload)
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "notif_tenant", "password": "notif-pass"},
    )
    tenant_token = tenant_login.json()["access_token"]

    await client.post(
        "/api/v1/bookings",
        json={"property_id": property_id, "scheduled_date": "2026-07-01"},
        headers={"Authorization": f"Bearer {tenant_token}"},
    )

    notif_resp = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert notif_resp.status_code == 200
    notifications = notif_resp.json()
    assert len(notifications) >= 1
    assert notifications[0]["type"] == "booking_created"


@pytest.mark.asyncio
async def test_mark_read_and_unread_count(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:

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

    for i in range(3):
        tenant_payload = {
            "username": f"count_tenant_{i}",
            "email": f"count_tenant_{i}@example.com",
            "password": "count-pass",
            "role": "tenant",
        }
        await client.post("/api/v1/auth/register", json=tenant_payload)
        tenant_login = await client.post(
            "/api/v1/auth/login",
            json={"username_or_email": f"count_tenant_{i}", "password": "count-pass"},
        )
        tenant_token = tenant_login.json()["access_token"]
        await client.post(
            "/api/v1/bookings",
            json={"property_id": property_id, "scheduled_date": "2026-07-01"},
            headers={"Authorization": f"Bearer {tenant_token}"},
        )

    count_resp = await client.get(
        "/api/v1/notifications/unread-count",
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert count_resp.status_code == 200
    assert count_resp.json()["count"] >= 3

    notifs = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    first_id = notifs.json()[0]["id"]

    read_resp = await client.patch(
        f"/api/v1/notifications/{first_id}/read",
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True

    await client.patch(
        "/api/v1/notifications/read-all",
        headers={"Authorization": f"Bearer {landlord_token}"},
    )

    final_count = await client.get(
        "/api/v1/notifications/unread-count",
        headers={"Authorization": f"Bearer {landlord_token}"},
    )
    assert final_count.json()["count"] == 0


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_notifications(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 401

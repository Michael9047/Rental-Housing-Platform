import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_property(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
    property_payload: dict[str, str | int],
) -> None:
    user_response = await client.post("/api/v1/auth/register", json=landlord_register_payload)
    landlord_id = user_response.json()["id"]
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]

    create_response = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == property_payload["title"]
    assert created["landlord_id"] == landlord_id

    list_response = await client.get("/api/v1/properties")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


@pytest.mark.asyncio
async def test_create_property_requires_existing_landlord(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    await client.post("/api/v1/auth/register", json=landlord_register_payload)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": landlord_register_payload["username"],
            "password": landlord_register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/properties",
        json={
            "landlord_id": 999,
            "title": "Ghost listing",
            "address": "No address",
            "district": "Unknown",
            "price_monthly": "1.00",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_create_property(
    client: AsyncClient,
    property_payload: dict[str, str | int],
) -> None:
    response = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": 1},
    )

    assert response.status_code == 401

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_without_query_returns_filtered_results(
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

    await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/properties/search",
        params={"district": "SIP", "bedrooms": 2},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["district"] == "SIP"
    assert results[0]["bedrooms"] == 2


@pytest.mark.asyncio
async def test_search_by_price_range(
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

    await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/properties/search",
        params={"price_min": "4000", "price_max": "6000"},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1

    empty_response = await client.get(
        "/api/v1/properties/search",
        params={"price_max": "1000"},
    )
    assert empty_response.status_code == 200
    assert len(empty_response.json()) == 0


@pytest.mark.asyncio
async def test_search_publicly_accessible(client: AsyncClient) -> None:
    response = await client.get("/api/v1/properties/search")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_by_property_type(
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

    await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": landlord_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/properties/search",
        params={"property_type": "apartment"},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["property_type"] == "apartment"
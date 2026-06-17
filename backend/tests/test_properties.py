import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_property(
    client: AsyncClient,
    landlord_payload: dict[str, str],
) -> None:
    user_response = await client.post("/api/v1/users", json=landlord_payload)
    landlord_id = user_response.json()["id"]

    property_payload = {
        "landlord_id": landlord_id,
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
    }

    create_response = await client.post("/api/v1/properties", json=property_payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == property_payload["title"]
    assert created["landlord_id"] == landlord_id

    list_response = await client.get("/api/v1/properties")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


@pytest.mark.asyncio
async def test_create_property_requires_existing_landlord(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/properties",
        json={
            "landlord_id": 999,
            "title": "Ghost listing",
            "address": "No address",
            "district": "Unknown",
            "price_monthly": "1.00",
        },
    )

    assert response.status_code == 422

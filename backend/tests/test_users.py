import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_get_update_delete_user(
    client: AsyncClient,
    landlord_payload: dict[str, str],
) -> None:
    create_response = await client.post("/api/v1/users", json=landlord_payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["username"] == "landlord_demo"
    assert created["role"] == "landlord"
    assert "password_hash" not in created

    user_id = created["id"]
    get_response = await client.get(f"/api/v1/users/{user_id}")
    assert get_response.status_code == 200

    update_response = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"phone": "+8613800000000"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["phone"] == "+8613800000000"

    delete_response = await client.delete(f"/api/v1/users/{user_id}")
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/api/v1/users/{user_id}")
    assert missing_response.status_code == 404

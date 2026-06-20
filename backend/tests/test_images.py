import io
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def registered_landlord(client: AsyncClient, landlord_register_payload: dict[str, str]):
    """Fixture that yields (user_data, token)."""
    async def _register():
        user_resp = await client.post("/api/v1/auth/register", json=landlord_register_payload)
        assert user_resp.status_code == 201
        user_data = user_resp.json()
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username_or_email": landlord_register_payload["username"],
                "password": landlord_register_payload["password"],
            },
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        return user_data, token
    return _register


@pytest.fixture
def fake_jpeg() -> io.BytesIO:
    """Create a minimal fake JPEG file."""
    return io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")


@pytest.fixture
async def property_with_landlord(
    client: AsyncClient,
    registered_landlord,
    property_payload: dict[str, str | int],
):
    """Register a landlord, create a property, return (property_data, token)."""
    user_data, token = await registered_landlord()
    create_resp = await client.post(
        "/api/v1/properties",
        json={**property_payload, "landlord_id": user_data["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    return create_resp.json(), token


@pytest.mark.asyncio
async def test_list_images_empty(
    client: AsyncClient,
    property_with_landlord,
):
    """Listing images on a property with no images returns empty list."""
    prop, _token = await property_with_landlord
    response = await client.get(f"/api/v1/properties/{prop['id']}/images")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_upload_image(
    client: AsyncClient,
    property_with_landlord,
    fake_jpeg,
):
    """Upload a single image and verify it becomes primary."""
    prop, token = await property_with_landlord

    fake_jpeg.seek(0)
    files = [("files", ("test.jpg", fake_jpeg, "image/jpeg"))]
    response = await client.post(
        f"/api/v1/properties/{prop['id']}/images",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    img = data[0]
    assert img["property_id"] == prop["id"]
    assert img["original_name"] == "test.jpg"
    assert img["mime_type"] == "image/jpeg"
    assert img["is_primary"] is True

    # Verify it appears in property detail
    prop_resp = await client.get(f"/api/v1/properties/{prop['id']}")
    assert prop_resp.status_code == 200
    prop_detail = prop_resp.json()
    assert len(prop_detail["images"]) == 1
    assert prop_detail["images"][0]["is_primary"] is True


@pytest.mark.asyncio
async def test_list_images(
    client: AsyncClient,
    property_with_landlord,
    fake_jpeg,
):
    """List images returns all uploaded images."""
    prop, token = await property_with_landlord

    for i in range(3):
        fake_jpeg.seek(0)
        files = [("files", (f"img{i}.jpg", io.BytesIO(fake_jpeg.read()), "image/jpeg"))]
        resp = await client.post(
            f"/api/v1/properties/{prop['id']}/images",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

    response = await client.get(f"/api/v1/properties/{prop['id']}/images")
    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_upload_wrong_type(
    client: AsyncClient,
    property_with_landlord,
):
    """Uploading a non-image file should be rejected."""
    prop, token = await property_with_landlord

    fake_file = io.BytesIO(b"this is a text file")
    files = [("files", ("test.txt", fake_file, "text/plain"))]
    response = await client.post(
        f"/api/v1/properties/{prop['id']}/images",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_image(
    client: AsyncClient,
    property_with_landlord,
    fake_jpeg,
):
    """Delete an uploaded image."""
    prop, token = await property_with_landlord

    fake_jpeg.seek(0)
    files = [("files", ("test.jpg", fake_jpeg, "image/jpeg"))]
    upload_resp = await client.post(
        f"/api/v1/properties/{prop['id']}/images",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    img = upload_resp.json()[0]

    # Delete it
    response = await client.delete(
        f"/api/v1/properties/{prop['id']}/images/{img['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    # Verify it's gone
    list_resp = await client.get(f"/api/v1/properties/{prop['id']}/images")
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_set_primary(
    client: AsyncClient,
    property_with_landlord,
    fake_jpeg,
):
    """Set a specific image as the primary/cover image."""
    prop, token = await property_with_landlord

    # Upload 2 images
    imgs = []
    for i in range(2):
        fake_jpeg.seek(0)
        files = [("files", (f"img{i}.jpg", io.BytesIO(fake_jpeg.read()), "image/jpeg"))]
        resp = await client.post(
            f"/api/v1/properties/{prop['id']}/images",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        imgs.extend(resp.json())

    # First image should be primary
    assert imgs[0]["is_primary"] is True
    assert imgs[1]["is_primary"] is False

    # Set second as primary
    response = await client.patch(
        f"/api/v1/properties/{prop['id']}/images/{imgs[1]['id']}/primary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["is_primary"] is True

    # Verify the switch
    list_resp = await client.get(f"/api/v1/properties/{prop['id']}/images")
    images = {img["id"]: img["is_primary"] for img in list_resp.json()}
    assert images[imgs[0]["id"]] is False
    assert images[imgs[1]["id"]] is True


@pytest.mark.asyncio
async def test_unauthorized_upload(
    client: AsyncClient,
    property_with_landlord,
    fake_jpeg,
):
    """Unauthenticated users cannot upload images."""
    prop, _token = await property_with_landlord

    fake_jpeg.seek(0)
    files = [("files", ("test.jpg", fake_jpeg, "image/jpeg"))]
    response = await client.post(
        f"/api/v1/properties/{prop['id']}/images",
        files=files,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_delete(
    client: AsyncClient,
    property_with_landlord,
    fake_jpeg,
):
    """Users without auth cannot delete images."""
    prop, token = await property_with_landlord

    fake_jpeg.seek(0)
    files = [("files", ("test.jpg", fake_jpeg, "image/jpeg"))]
    upload_resp = await client.post(
        f"/api/v1/properties/{prop['id']}/images",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    img = upload_resp.json()[0]

    response = await client.delete(
        f"/api/v1/properties/{prop['id']}/images/{img['id']}",
    )
    assert response.status_code == 401

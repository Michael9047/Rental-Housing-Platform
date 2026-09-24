"""BM 公寓与户型上下架接口测试。"""
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.building_image import BuildingImage
from app.models.institute import Institute, InstituteStatus
from app.models.unit_type import PropertyType, UnitType, UnitTypeStatus


async def _landlord(client: AsyncClient, username: str = "lifecycle_owner") -> tuple[int, dict[str, str]]:
    email = f"{username}@example.com"
    registered = await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": "secure-password",
        "role": "landlord",
    })
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "secure-password"})
    assert login.status_code == 200, login.text
    return registered.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _listing(session: AsyncSession, owner_id: int, *, with_image: bool = True) -> tuple[int, int]:
    building = Institute(
        name="生命周期测试公寓",
        address="1 Test Street, Singapore",
        country="新加坡",
        city="新加坡",
        street="1 Test Street",
        latitude=Decimal("1.300000"),
        longitude=Decimal("103.800000"),
        status=InstituteStatus.active,
        created_by=owner_id,
    )
    session.add(building)
    await session.flush()
    if with_image:
        session.add(BuildingImage(
            institute_id=building.id,
            filename="building.jpg",
            original_name="building.jpg",
            mime_type="image/jpeg",
            file_size=100,
            sort_order=0,
            is_primary=True,
        ))
    unit_type = UnitType(
        institute_id=building.id,
        name="Studio A",
        property_type=PropertyType.studio.value,
        base_rent=Decimal("1500"),
        currency="SGD",
        total_count=1,
        available_count=1,
        available_from=date(2026, 9, 1),
        image_urls=["unit.jpg"],
        status=UnitTypeStatus.available,
    )
    session.add(unit_type)
    await session.commit()
    return building.id, unit_type.id


@pytest.mark.asyncio
async def test_building_offline_preserves_child_status_and_can_publish(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    owner_id, headers = await _landlord(client)
    async with session_maker() as session:
        building_id, unit_type_id = await _listing(session, owner_id)

    offline = await client.post(f"/api/v1/buildings/{building_id}/offline", headers=headers)
    assert offline.status_code == 200, offline.text
    assert offline.json()["status"] == "offline"

    async with session_maker() as session:
        child = await session.get(UnitType, unit_type_id)
        assert child.status == UnitTypeStatus.available

    published = await client.post(f"/api/v1/buildings/{building_id}/publish", headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "active"


@pytest.mark.asyncio
async def test_publish_returns_exact_missing_fields(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    owner_id, headers = await _landlord(client, "incomplete_owner")
    async with session_maker() as session:
        building_id, _ = await _listing(session, owner_id, with_image=False)
        building = await session.get(Institute, building_id)
        building.status = InstituteStatus.offline
        await session.commit()

    response = await client.post(f"/api/v1/buildings/{building_id}/publish", headers=headers)
    assert response.status_code == 422, response.text
    error_message = response.json()["error"]["message"]
    assert "missing_fields" in error_message
    assert "images" in error_message


@pytest.mark.asyncio
async def test_unit_type_can_be_offlined_and_published_independently(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    owner_id, headers = await _landlord(client, "unit_owner")
    async with session_maker() as session:
        _, unit_type_id = await _listing(session, owner_id)

    offline = await client.post(f"/api/v1/unit-types/{unit_type_id}/offline", headers=headers)
    assert offline.status_code == 200, offline.text
    assert offline.json()["status"] == "offline"

    published = await client.post(f"/api/v1/unit-types/{unit_type_id}/publish", headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "available"

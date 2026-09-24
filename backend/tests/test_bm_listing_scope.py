"""BM 公寓与户型管理范围隔离测试。"""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.institute import Institute, InstituteStatus
from app.models.unit_type import UnitType, UnitTypeStatus


async def _register_landlord(client: AsyncClient, username: str) -> tuple[int, dict[str, str]]:
    response = await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secure-password",
        "role": "landlord",
    })
    assert response.status_code == 201, response.text
    login = await client.post("/api/v1/auth/login", json={
        "username_or_email": username,
        "password": "secure-password",
    })
    assert login.status_code == 200, login.text
    return response.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _create_listing(session: AsyncSession, owner_id: int, suffix: str) -> tuple[int, int]:
    building = Institute(
        name=f"{suffix}公寓",
        country="Singapore",
        city="Singapore",
        street=f"{suffix} Street",
        status=InstituteStatus.active,
        created_by=owner_id,
        bm_id=owner_id,
    )
    session.add(building)
    await session.flush()
    unit_type = UnitType(
        institute_id=building.id,
        name=f"{suffix}户型",
        property_type="studio",
        base_rent=Decimal("1200"),
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
async def test_landlord_lists_only_unit_types_from_managed_buildings(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    owner_id, owner_headers = await _register_landlord(client, "scope_owner")
    other_id, other_headers = await _register_landlord(client, "scope_other")
    async with session_maker() as session:
        _, owner_unit_id = await _create_listing(session, owner_id, "Owner")
        _, other_unit_id = await _create_listing(session, other_id, "Other")

    owner_response = await client.get("/api/v1/unit-types", headers=owner_headers)
    other_response = await client.get("/api/v1/unit-types", headers=other_headers)

    assert [item["id"] for item in owner_response.json()["items"]] == [owner_unit_id]
    assert [item["id"] for item in other_response.json()["items"]] == [other_unit_id]


@pytest.mark.asyncio
async def test_landlord_cannot_mutate_another_bm_unit_type(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    owner_id, _ = await _register_landlord(client, "mutation_owner")
    _, other_headers = await _register_landlord(client, "mutation_other")
    async with session_maker() as session:
        owner_building_id, owner_unit_id = await _create_listing(session, owner_id, "Private")
        unit_type = await session.get(UnitType, owner_unit_id)
        unit_type.deleted_at = datetime.now(UTC)
        await session.commit()

    create_response = await client.post("/api/v1/unit-types", headers=other_headers, json={
        "institute_id": owner_building_id,
        "name": "越权新建",
        "property_type": "studio",
        "base_rent": "1300",
    })
    update_response = await client.patch(
        f"/api/v1/unit-types/{owner_unit_id}", headers=other_headers, json={"name": "越权编辑"}
    )
    restore_response = await client.post(f"/api/v1/unit-types/{owner_unit_id}/restore", headers=other_headers)
    copy_response = await client.post(f"/api/v1/unit-types/{owner_unit_id}/copy", headers=other_headers)

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert restore_response.status_code == 403
    assert copy_response.status_code == 403


@pytest.mark.asyncio
async def test_new_building_is_assigned_to_current_bm_and_lists_are_scoped(
    client: AsyncClient,
) -> None:
    owner_id, owner_headers = await _register_landlord(client, "building_owner")
    other_id, other_headers = await _register_landlord(client, "building_other")

    created = await client.post("/api/v1/buildings", headers=owner_headers, json={
        "name": "自动归属公寓",
        "country": "Singapore",
        "city": "Singapore",
        "street": "1 Scope Street",
        "bm_id": other_id,
    })
    assert created.status_code == 200, created.text
    assert created.json()["bm_id"] == owner_id

    owner_list = await client.get("/api/v1/buildings", headers=owner_headers)
    other_list = await client.get("/api/v1/buildings", headers=other_headers)
    assert [item["id"] for item in owner_list.json()] == [created.json()["id"]]
    assert other_list.json() == []

    forbidden_get = await client.get(f"/api/v1/buildings/{created.json()['id']}", headers=other_headers)
    assert forbidden_get.status_code == 403

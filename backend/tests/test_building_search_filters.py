"""公开 Building 搜索的 UnitType 条件同步回归测试。"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.institute import Institute, InstituteStatus
from app.models.booking import Booking, BookingStatus
from app.models.unit_type import PropertyType, UnitType, UnitTypeStatus


async def _register_creator(client: AsyncClient) -> int:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "building_search_owner",
            "email": "building-search@example.com",
            "password": "secure-password",
            "role": "landlord",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _add_institute(
    session: AsyncSession,
    creator_id: int,
    *,
    name: str,
    amenities: list[str] | None = None,
) -> Institute:
    institute = Institute(
        name=name,
        address=f"{name} address",
        country="SG",
        city="Singapore",
        district="Queenstown",
        amenities=amenities or [],
        status=InstituteStatus.active,
        created_by=creator_id,
    )
    session.add(institute)
    await session.flush()
    return institute


async def _add_unit_type(
    session: AsyncSession,
    institute: Institute,
    *,
    name: str,
    price: int,
    property_type: str,
    amenities: list[str] | None = None,
    status: UnitTypeStatus = UnitTypeStatus.available,
    has_vacancy: bool = True,
    available_count: int = 1,
) -> UnitType:
    unit_type = UnitType(
        institute_id=institute.id,
        name=name,
        base_rent=Decimal(price),
        property_type=property_type,
        bedrooms=0 if property_type == PropertyType.studio.value else 1,
        bathrooms=1,
        hall_count=0,
        amenities=amenities or [],
        status=status,
        has_vacancy=has_vacancy,
        total_count=max(available_count, 1),
        available_count=available_count,
        min_stay_months=3,
    )
    session.add(unit_type)
    await session.flush()
    return unit_type


@pytest.mark.asyncio
async def test_building_search_uses_one_rentable_unit_and_filters_before_limit(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    creator_id = await _register_creator(client)

    async with session_maker() as session:
        matching = await _add_institute(
            session,
            creator_id,
            name="Matching Residence",
            amenities=["WiFi", "空调"],
        )
        # 先放一个不匹配户型，使命中的 UnitType ID 与 Institute ID 明确不同。
        await _add_unit_type(
            session,
            matching,
            name="Expensive one bed",
            price=6000,
            property_type=PropertyType._1bed.value,
            amenities=["空调"],
        )
        matched_unit = await _add_unit_type(
            session,
            matching,
            name="Matching studio",
            price=2500,
            property_type=PropertyType.studio.value,
            amenities=["空调"],
        )

        split_match = await _add_institute(
            session,
            creator_id,
            name="Split Match Residence",
            amenities=["WiFi", "空调"],
        )
        await _add_unit_type(
            session,
            split_match,
            name="Affordable wrong type",
            price=2500,
            property_type=PropertyType._1bed.value,
            amenities=["空调"],
        )
        await _add_unit_type(
            session,
            split_match,
            name="Right type wrong price",
            price=6000,
            property_type=PropertyType.studio.value,
            amenities=["空调"],
        )

        unavailable = await _add_institute(
            session,
            creator_id,
            name="Unavailable Residence",
            amenities=["WiFi", "空调"],
        )
        await _add_unit_type(
            session,
            unavailable,
            name="No vacancy studio",
            price=2500,
            property_type=PropertyType.studio.value,
            amenities=["空调"],
            has_vacancy=False,
            available_count=0,
        )

        missing_amenity = await _add_institute(
            session,
            creator_id,
            name="Missing Amenity Residence",
            amenities=["WiFi"],
        )
        await _add_unit_type(
            session,
            missing_amenity,
            name="No aircon studio",
            price=2500,
            property_type=PropertyType.studio.value,
        )
        await session.commit()

        matching_id = matching.id
        matched_unit_id = matched_unit.id
        unavailable_id = unavailable.id

    response = await client.get(
        "/api/v1/buildings/public/search",
        params=[
            ("price_min", "2000"),
            ("price_max", "3000"),
            ("property_type", "studio"),
            ("amenities", "wifi"),
            ("amenities", "空调"),
            ("limit", "1"),
        ],
    )

    assert response.status_code == 200, response.text
    results = response.json()
    assert [item["id"] for item in results] == [matching_id]
    assert results[0]["institute_id"] == matching_id
    assert matched_unit_id != matching_id
    assert results[0]["id"] != matched_unit_id
    assert results[0]["representative_unit_type_id"] == matched_unit_id

    no_vacancy_response = await client.get(
        "/api/v1/buildings/public/search",
        params={"institute_id": unavailable_id},
    )
    assert no_vacancy_response.status_code == 200, no_vacancy_response.text
    assert no_vacancy_response.json() == []


@pytest.mark.asyncio
async def test_building_search_supports_exact_institute_id(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    creator_id = await _register_creator(client)

    async with session_maker() as session:
        first = await _add_institute(session, creator_id, name="First Residence")
        await _add_unit_type(
            session,
            first,
            name="First studio",
            price=2200,
            property_type=PropertyType.studio.value,
        )
        target = await _add_institute(session, creator_id, name="Target Residence")
        await _add_unit_type(
            session,
            target,
            name="Target studio",
            price=2300,
            property_type=PropertyType.studio.value,
        )
        await session.commit()
        first_id = first.id
        target_id = target.id

    response = await client.get(
        "/api/v1/buildings/public/search",
        params={"institute_id": target_id},
    )

    assert response.status_code == 200, response.text
    assert [(item["id"], item["name"]) for item in response.json()] == [
        (target_id, "Target Residence")
    ]

    multiple_response = await client.get(
        "/api/v1/buildings/public/search",
        params=[
            ("institute_ids", first_id),
            ("institute_ids", target_id),
        ],
    )
    assert multiple_response.status_code == 200, multiple_response.text
    assert {item["id"] for item in multiple_response.json()} == {first_id, target_id}


@pytest.mark.asyncio
async def test_building_search_excludes_unit_type_filled_by_signed_booking(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    creator_id = await _register_creator(client)

    async with session_maker() as session:
        building = await _add_institute(session, creator_id, name="Fully Booked Residence")
        unit_type = await _add_unit_type(
            session,
            building,
            name="Only studio",
            price=2500,
            property_type=PropertyType.studio.value,
            available_count=1,
        )
        session.add(
            Booking(
                user_id=creator_id,
                unit_type_id=unit_type.id,
                institute_id=building.id,
                status=BookingStatus.contract_signed,
            )
        )
        await session.commit()
        building_id = building.id

    response = await client.get(
        "/api/v1/buildings/public/search",
        params={"institute_id": building_id},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
async def test_building_card_uses_lowest_price_rentable_unit_without_filters(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    creator_id = await _register_creator(client)

    async with session_maker() as session:
        building = await _add_institute(session, creator_id, name="Representative Residence")
        await _add_unit_type(
            session,
            building,
            name="Unavailable bargain",
            price=900,
            property_type=PropertyType.studio.value,
            has_vacancy=False,
            available_count=0,
        )
        await _add_unit_type(
            session,
            building,
            name="Available expensive",
            price=3200,
            property_type=PropertyType._1bed.value,
        )
        cheapest_rentable = await _add_unit_type(
            session,
            building,
            name="Available cheapest",
            price=1800,
            property_type=PropertyType.studio.value,
        )
        await session.commit()
        building_id = building.id
        cheapest_rentable_id = cheapest_rentable.id

    response = await client.get(
        "/api/v1/buildings/public/search",
        params={"institute_id": building_id},
    )

    assert response.status_code == 200, response.text
    result = response.json()[0]
    assert result["id"] == building_id
    assert result["representative_unit_type_id"] == cheapest_rentable_id


@pytest.mark.asyncio
async def test_public_building_list_paginates_in_database_before_relationship_loads(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    creator_id = await _register_creator(client)

    async with session_maker() as session:
        first = await _add_institute(session, creator_id, name="First Residence")
        middle = await _add_institute(session, creator_id, name="Middle Residence")
        last = await _add_institute(session, creator_id, name="Last Residence")
        for institute, price in ((first, 2100), (middle, 2200), (last, 2300)):
            await _add_unit_type(
                session,
                institute,
                name=f"{institute.name} studio",
                price=price,
                property_type=PropertyType.studio.value,
            )
        await session.commit()
        expected_id = middle.id
        assert [first.id, middle.id, last.id] == sorted([first.id, middle.id, last.id])

    statements: list[str] = []
    engine = session_maker.kw["bind"]

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        response = await client.get(
            "/api/v1/buildings/public",
            params={"skip": 1, "limit": 1},
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [expected_id], statements

    root_queries = [
        statement.upper()
        for statement in statements
        if "FROM INSTITUTES" in statement.upper()
        and "INSTITUTES.STATUS" in statement.upper()
    ]
    assert root_queries
    assert "LIMIT" in root_queries[0]
    assert "OFFSET" in root_queries[0]


@pytest.mark.asyncio
async def test_price_sort_is_applied_before_database_limit(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    creator_id = await _register_creator(client)

    async with session_maker() as session:
        affordable = await _add_institute(session, creator_id, name="Affordable Residence")
        await _add_unit_type(
            session,
            affordable,
            name="Affordable studio",
            price=1800,
            property_type=PropertyType.studio.value,
        )
        expensive = await _add_institute(session, creator_id, name="Expensive Residence")
        await _add_unit_type(
            session,
            expensive,
            name="Expensive studio",
            price=6800,
            property_type=PropertyType.studio.value,
        )
        await session.commit()
        affordable_id = affordable.id

    response = await client.get(
        "/api/v1/buildings/public/search",
        params={"sort_by": "price_asc", "limit": 1},
    )

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [affordable_id]

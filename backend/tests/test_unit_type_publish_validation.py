"""户型创建必填字段与库存约束测试。"""
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.institute import Institute
from app.models.user import User, UserRole
from app.schemas.unit_type import UnitTypeCreate
from app.services.unit_type_service import UnitTypeService


def test_property_type_is_required() -> None:
    with pytest.raises(ValidationError):
        UnitTypeCreate(institute_id=1, name="Studio", base_rent=1000)


def test_available_count_cannot_exceed_total_count() -> None:
    with pytest.raises(ValidationError, match="可租套数"):
        UnitTypeCreate(
            institute_id=1, name="Studio", property_type="studio",
            base_rent=1000, total_count=1, available_count=2,
        )


@pytest.mark.asyncio
async def test_create_persists_type_and_inventory(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        owner = User(username="inventory_owner", email="inventory@example.com", password_hash="x", role=UserRole.landlord)
        session.add(owner)
        await session.flush()
        building = Institute(name="库存测试公寓", created_by=owner.id)
        session.add(building)
        await session.flush()
        unit_type = await UnitTypeService(session).create(UnitTypeCreate(
            institute_id=building.id, name="Studio", property_type="studio",
            base_rent=1000, total_count=3, available_count=2,
        ))
        assert getattr(unit_type.property_type, "value", unit_type.property_type) == "studio"
        assert unit_type.total_count == 3
        assert unit_type.available_count == 2

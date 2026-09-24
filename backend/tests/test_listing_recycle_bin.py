"""公寓回收站批次恢复与永久删除规则测试。"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.institute import Institute, InstituteStatus
from app.models.listing_deletion import ListingDeletionBatch
from app.models.unit_type import PropertyType, UnitType, UnitTypeStatus
from app.models.user import User, UserRole
from app.services.listing_lifecycle_service import ListingLifecycleError, ListingLifecycleService


async def _records(session: AsyncSession) -> tuple[User, Institute, UnitType, UnitType]:
    owner = User(username="recycle_owner", email="recycle@example.com", password_hash="x", role=UserRole.landlord)
    session.add(owner)
    await session.flush()
    building = Institute(
        name="回收站公寓", country="SG", city="Singapore", street="Test",
        status=InstituteStatus.active, created_by=owner.id,
    )
    session.add(building)
    await session.flush()
    common = dict(
        institute_id=building.id,
        property_type=PropertyType.studio.value,
        base_rent=Decimal("1000"),
        total_count=1,
        available_count=1,
        available_from=date(2026, 9, 1),
    )
    previously_deleted = UnitType(name="此前删除", status=UnitTypeStatus.maintenance, **common)
    cascaded = UnitType(name="本次级联", status=UnitTypeStatus.offline, **common)
    session.add_all([previously_deleted, cascaded])
    await session.flush()
    previously_deleted.deleted_at = datetime.now(timezone.utc) - timedelta(days=5)
    await session.commit()
    return owner, building, previously_deleted, cascaded


@pytest.mark.asyncio
async def test_restore_only_restores_unit_types_from_same_deletion_batch(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        owner, building, previously_deleted, cascaded = await _records(session)
        service = ListingLifecycleService(session)
        batch = await service.move_building_to_recycle_bin(building.id, owner)
        assert [item["id"] for item in batch.unit_types] == [cascaded.id]

        restored_building, restored_count = await service.restore_building_from_recycle_bin(building.id, owner)
        await session.refresh(previously_deleted)
        await session.refresh(cascaded)
        assert restored_building.status == InstituteStatus.active
        assert restored_count == 1
        assert previously_deleted.deleted_at is not None
        assert cascaded.deleted_at is None
        assert cascaded.status == UnitTypeStatus.offline


@pytest.mark.asyncio
async def test_hard_delete_requires_thirty_days_in_recycle_bin(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        owner, building, _previously_deleted, _cascaded = await _records(session)
        service = ListingLifecycleService(session)
        batch = await service.move_building_to_recycle_bin(building.id, owner)
        with pytest.raises(ListingLifecycleError, match="30"):
            await service.ensure_hard_delete_allowed(building_id=building.id)
        batch.created_at = datetime.now(timezone.utc) - timedelta(days=31)
        await session.commit()
        await service.ensure_hard_delete_allowed(building_id=building.id)

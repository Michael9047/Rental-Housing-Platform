"""统一管理公寓与户型的上架、下架及发布资料校验。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.building_image import BuildingImage
from app.models.institute import Institute, InstituteStatus
from app.models.listing_deletion import ListingDeletionBatch
from app.models.unit_type import UnitType, UnitTypeStatus
from app.services.institute_access import can_manage_institute
from app.services.property_service import _bump_search_cache_version


@dataclass(frozen=True)
class PublishValidation:
    valid: bool
    missing_fields: tuple[str, ...]


class ListingLifecycleError(ValueError):
    """生命周期操作无法完成，并携带适合接口返回的错误信息。"""

    def __init__(self, message: str, *, missing_fields: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields


def validate_building_publishable(building: Institute, image_count: int) -> PublishValidation:
    """校验公寓重新上架所需的最小资料。"""
    missing: list[str] = []
    if not (building.name or "").strip():
        missing.append("name")
    if not (building.country or "").strip():
        missing.append("country")
    if not (building.city or "").strip():
        missing.append("city")
    if not (building.street or "").strip():
        missing.append("street")
    if building.latitude is None:
        missing.append("latitude")
    if building.longitude is None:
        missing.append("longitude")
    if image_count < 1:
        missing.append("images")
    return PublishValidation(not missing, tuple(missing))


def validate_unit_type_publishable(unit_type: UnitType) -> PublishValidation:
    """校验户型重新上架所需的最小资料。"""
    missing: list[str] = []
    if not unit_type.institute_id:
        missing.append("institute_id")
    if not unit_type.property_type:
        missing.append("property_type")
    if unit_type.base_rent is None:
        missing.append("base_rent")
    if not (unit_type.currency or "").strip():
        missing.append("currency")
    if unit_type.total_count is None:
        missing.append("total_count")
    if unit_type.available_count is None:
        missing.append("available_count")
    if unit_type.available_from is None:
        missing.append("available_from")
    if not unit_type.image_urls:
        missing.append("image_urls")
    return PublishValidation(not missing, tuple(missing))


class ListingLifecycleService:
    """在单一事务内执行状态变化、权限检查与审计记录。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _managed_building(self, building_id: int, user) -> Institute:
        building = await self.session.get(Institute, building_id)
        if not building:
            raise ListingLifecycleError("公寓不存在")
        if not await can_manage_institute(self.session, user, building_id):
            raise PermissionError("无权管理该公寓")
        return building

    async def _managed_unit_type(self, unit_type_id: int, user) -> UnitType:
        unit_type = await self.session.get(UnitType, unit_type_id)
        if not unit_type or unit_type.deleted_at is not None:
            raise ListingLifecycleError("户型不存在")
        if not await can_manage_institute(self.session, user, unit_type.institute_id):
            raise PermissionError("无权管理该户型")
        return unit_type

    async def _audit(self, user_id: int, action: str, resource_type: str, resource_id: int, old_status: str, new_status: str) -> None:
        self.session.add(AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details={"old_status": old_status, "new_status": new_status},
        ))

    async def offline_building(self, building_id: int, user) -> Institute:
        building = await self._managed_building(building_id, user)
        if building.status == InstituteStatus.suspended:
            raise ListingLifecycleError("回收站中的公寓不能下架")
        old = building.status.value
        building.status = InstituteStatus.offline
        await self._audit(user.id, "building_offline", "building", building.id, old, building.status.value)
        await self.session.commit()
        await self.session.refresh(building)
        await _bump_search_cache_version()
        return building

    async def publish_building(self, building_id: int, user) -> Institute:
        building = await self._managed_building(building_id, user)
        if building.status == InstituteStatus.suspended:
            raise ListingLifecycleError("请先从回收站恢复公寓")
        image_count = await self.session.scalar(
            select(func.count(BuildingImage.id)).where(BuildingImage.institute_id == building.id)
        ) or 0
        validation = validate_building_publishable(building, image_count)
        if not validation.valid:
            raise ListingLifecycleError("公寓资料不完整，无法上架", missing_fields=validation.missing_fields)
        old = building.status.value
        building.status = InstituteStatus.active
        await self._audit(user.id, "building_publish", "building", building.id, old, building.status.value)
        await self.session.commit()
        await self.session.refresh(building)
        await _bump_search_cache_version()
        return building

    async def offline_unit_type(self, unit_type_id: int, user) -> UnitType:
        unit_type = await self._managed_unit_type(unit_type_id, user)
        old = unit_type.status.value
        unit_type.status = UnitTypeStatus.offline
        await self._audit(user.id, "unit_type_offline", "unit_type", unit_type.id, old, unit_type.status.value)
        await self.session.commit()
        await self.session.refresh(unit_type)
        await _bump_search_cache_version()
        return unit_type

    async def publish_unit_type(self, unit_type_id: int, user) -> UnitType:
        unit_type = await self._managed_unit_type(unit_type_id, user)
        validation = validate_unit_type_publishable(unit_type)
        if not validation.valid:
            raise ListingLifecycleError("户型资料不完整，无法上架", missing_fields=validation.missing_fields)
        old = unit_type.status.value
        unit_type.status = UnitTypeStatus.available
        await self._audit(user.id, "unit_type_publish", "unit_type", unit_type.id, old, unit_type.status.value)
        await self.session.commit()
        await self.session.refresh(unit_type)
        await _bump_search_cache_version()
        return unit_type

    async def has_business_history(self, *, building_id: int | None = None, unit_type_id: int | None = None) -> bool:
        statement = select(func.count(Booking.id))
        if unit_type_id is not None:
            statement = statement.where(Booking.unit_type_id == unit_type_id)
        elif building_id is not None:
            statement = statement.where(Booking.institute_id == building_id)
        else:
            raise ValueError("必须提供 building_id 或 unit_type_id")
        return bool(await self.session.scalar(statement))

    async def move_building_to_recycle_bin(self, building_id: int, user) -> ListingDeletionBatch:
        """记录本次实际级联户型，避免恢复历史上已单独删除的户型。"""
        building = await self._managed_building(building_id, user)
        if await self.has_business_history(building_id=building_id):
            raise ListingLifecycleError("该公寓已有订单记录，不能删除，请改用下架")
        unit_types = list((await self.session.scalars(
            select(UnitType).where(UnitType.institute_id == building_id, UnitType.deleted_at.is_(None))
        )).all())
        batch = ListingDeletionBatch(
            building_id=building.id,
            building_status=building.status.value,
            unit_types=[{"id": item.id, "status": item.status.value} for item in unit_types],
            created_by=user.id,
        )
        self.session.add(batch)
        deleted_at = datetime.now(timezone.utc)
        for item in unit_types:
            item.deleted_at = deleted_at
        building.status = InstituteStatus.suspended
        await self.session.commit()
        await self.session.refresh(batch)
        await _bump_search_cache_version()
        return batch

    async def restore_building_from_recycle_bin(self, building_id: int, user) -> tuple[Institute, int]:
        """仅恢复最近一次未恢复删除批次中包含的户型。"""
        building = await self._managed_building(building_id, user)
        if building.status != InstituteStatus.suspended:
            raise ListingLifecycleError("该公寓不在回收站中")
        batch = await self.session.scalar(
            select(ListingDeletionBatch).where(
                ListingDeletionBatch.building_id == building_id,
                ListingDeletionBatch.restored_at.is_(None),
            ).order_by(ListingDeletionBatch.id.desc())
        )
        if not batch:
            raise ListingLifecycleError("未找到该公寓的删除批次")
        building.status = InstituteStatus(batch.building_status)
        restored = 0
        for snapshot in batch.unit_types:
            unit_type = await self.session.get(UnitType, snapshot["id"])
            if unit_type and unit_type.deleted_at is not None:
                unit_type.deleted_at = None
                unit_type.status = UnitTypeStatus(snapshot["status"])
                restored += 1
        batch.restored_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(building)
        await _bump_search_cache_version()
        return building, restored

    async def ensure_hard_delete_allowed(
        self, *, building_id: int | None = None, unit_type_id: int | None = None
    ) -> None:
        """永久删除仅允许回收站保留满 30 天且不存在业务历史的对象。"""
        if await self.has_business_history(building_id=building_id, unit_type_id=unit_type_id):
            raise ListingLifecycleError("该对象已有业务历史，不能永久删除")
        if building_id is not None:
            batch = await self.session.scalar(
                select(ListingDeletionBatch).where(
                    ListingDeletionBatch.building_id == building_id,
                    ListingDeletionBatch.restored_at.is_(None),
                ).order_by(ListingDeletionBatch.id.desc())
            )
            deleted_at = batch.created_at if batch else None
        else:
            unit_type = await self.session.get(UnitType, unit_type_id)
            deleted_at = unit_type.deleted_at if unit_type else None
        if deleted_at is not None and deleted_at.tzinfo is None:
            deleted_at = deleted_at.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        if deleted_at is None or deleted_at > cutoff:
            raise ListingLifecycleError("进入回收站满 30 天后才可永久删除")

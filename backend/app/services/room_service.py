"""房间服务层"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from sqlalchemy.orm import selectinload

from app.models.property import Room, RoomStatus
from app.models.property_image import RoomImage
from app.schemas.room import RoomCreate, RoomUpdate


class RoomService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _audit(self, action: str, resource_id: int, details: dict | None = None):
        try:
            log = AuditLog(action=action, resource_type="room", resource_id=resource_id, details=details)
            self.session.add(log)
            await self.session.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Audit log failed: {e}")

    async def create(self, data: RoomCreate) -> Room:
        room = Room(
            landlord_id=data.landlord_id,
            unit_type_id=data.unit_type_id,
            room_number=data.room_number,
            building_block=data.building_block,
            floor=data.floor,
            special_discount=data.special_discount,
            available_from=data.available_from,
            min_stay_months=data.min_stay_months,
            status=data.status,
        )
        self.session.add(room)
        await self.session.commit()
        # 加载户型名和公寓名
        ut_name = ''
        inst_name = ''
        try:
            from app.models.unit_type import UnitType
            ut = await self.session.get(UnitType, room.unit_type_id, options=[selectinload(UnitType.institute)])
            if ut:
                ut_name = ut.name
                if ut.institute: inst_name = ut.institute.name
        except Exception: pass
        desc = f"在「{inst_name}」公寓的「{ut_name}」户型下创建了房间「{room.room_number}」"
        if room.floor is not None: desc += f"，位于第{room.floor}层"
        await self._audit("创建房间", room.id, {"描述": desc, "房号": room.room_number, "楼层": room.floor, "公寓": inst_name, "户型": ut_name})
        # 预加载关联数据以避免 _to_read 中的 MissingGreenlet
        from app.models.unit_type import UnitType
        from app.models.institute import Institute
        ut = await self.session.get(UnitType, room.unit_type_id, options=[selectinload(UnitType.institute)])
        if ut:
            room._ut_name = ut.name
            room._ut_base_rent = ut.base_rent
            room._ut_area_sqm = ut.area_sqm
            room._ut_bedrooms = ut.bedrooms
            room._ut_bathrooms = ut.bathrooms
            room._ut_hall_count = ut.hall_count
            room._ut_deposit_amount = ut.deposit_amount
            room._ut_amenities = ut.amenities
            if ut.institute:
                room._inst_id = ut.institute.id
                room._inst_name = ut.institute.name
                room._inst_address = ut.institute.address
        return room

    async def check_duplicate(self, unit_type_id: int, room_number: str, exclude_id: int | None = None) -> bool:
        """检查同户型下是否已存在相同房号"""
        from sqlalchemy import and_
        filters = [
            Room.unit_type_id == unit_type_id,
            Room.room_number == room_number,
            Room.deleted_at.is_(None),
        ]
        if exclude_id:
            filters.append(Room.id != exclude_id)
        stmt = select(func.count(Room.id)).where(and_(*filters))
        count = (await self.session.scalar(stmt)) or 0
        return count > 0

    async def get(self, room_id: int) -> Room | None:
        stmt = (
            select(Room)
            .options(
                selectinload(Room.unit_type).selectinload(Room.unit_type.property.mapper.class_.institute)
                if hasattr(Room.unit_type.property.mapper.class_, 'institute') else selectinload(Room.unit_type),
                selectinload(Room.images),
            )
            .where(Room.id == room_id)
        )
        result = await self.session.scalars(stmt)
        return result.unique().first()

    async def list(
        self, *, skip: int = 0, limit: int = 20,
        unit_type_id: int | None = None,
        institute_id: int | None = None,
        landlord_id: int | None = None,
        status: str | None = None,
        include_deleted: bool = False,
    ) -> dict:
        from app.models.unit_type import UnitType

        filters = []
        if not include_deleted:
            filters.append(Room.deleted_at.is_(None))
        if unit_type_id is not None:
            filters.append(Room.unit_type_id == unit_type_id)
        if landlord_id is not None:
            filters.append(Room.landlord_id == landlord_id)
        if status:
            filters.append(Room.status == status)

        # 公寓过滤：join unit_types
        if institute_id is not None:
            filters.append(UnitType.institute_id == institute_id)

        base = select(func.count(Room.id))
        if institute_id is not None:
            base = base.join(UnitType, Room.unit_type_id == UnitType.id)
        for f in filters:
            base = base.where(f)
        total = (await self.session.scalar(base)) or 0

        stmt = (
            select(Room)
            .options(
                selectinload(Room.images),
                selectinload(Room.unit_type).selectinload(UnitType.institute),
            )
            .order_by(Room.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if institute_id is not None:
            stmt = stmt.join(UnitType, Room.unit_type_id == UnitType.id)
        for f in filters:
            stmt = stmt.where(f)

        result = await self.session.scalars(stmt)
        items = list(result.unique())
        return {"items": items, "total": total, "page": skip // limit + 1,
                "page_size": limit, "total_pages": max(1, (total + limit - 1) // limit)}

    async def update(self, room_id: int, data: RoomUpdate) -> Room | None:
        room = await self.get(room_id)
        if not room:
            return None

        # 乐观锁
        if data.version is not None and data.version != room.version:
            from fastapi import HTTPException
            raise HTTPException(409, "数据已被他人修改，请刷新后重试")

        update_data = data.model_dump(exclude_unset=True, exclude={"version"})
        # 先记录旧值，再应用修改
        old_vals = {k: str(getattr(room, k, '')) for k in update_data}
        for k, v in update_data.items():
            setattr(room, k, v)
        room.version += 1
        await self.session.commit()
        await self.session.refresh(room)
        # 生成大白话描述
        desc_parts = []
        for k, v in update_data.items():
            old_val = old_vals.get(k, '')
            if k == 'room_number': desc_parts.append(f"房号从「{old_val}」改为「{v}」")
            elif k == 'floor': desc_parts.append(f"楼层从「{old_val}」改为「{v}」")
            elif k == 'special_discount': desc_parts.append(f"专属优惠从「{old_val}」改为「{v}」")
            elif k == 'available_from': desc_parts.append(f"可入住日期从「{old_val}」改为「{v}」")
            elif k == 'status': desc_parts.append(f"状态从「{old_val}」改为「{v}」")
            else: desc_parts.append(f"「{k}」从「{old_val}」改为「{v}」")
        desc = f"修改了房间「{room.room_number}」：{'；'.join(desc_parts)}"
        await self._audit("编辑房间", room.id, {"描述": desc, "房号": room.room_number, "修改内容": {k: {"新值": str(v), "旧值": old_vals.get(k, '')} for k, v in update_data.items()}})
        # 预加载关联数据用于 _to_read
        from app.models.unit_type import UnitType
        from app.models.institute import Institute
        ut = await self.session.get(UnitType, room.unit_type_id, options=[selectinload(UnitType.institute)])
        if ut:
            room._ut_name = ut.name
            room._ut_base_rent = ut.base_rent
            room._ut_area_sqm = ut.area_sqm
            room._ut_bedrooms = ut.bedrooms; room._ut_bathrooms = ut.bathrooms
            room._ut_hall_count = ut.hall_count; room._ut_deposit_amount = ut.deposit_amount
            room._ut_amenities = ut.amenities
            if ut.institute:
                room._inst_id = ut.institute.id; room._inst_name = ut.institute.name
                room._inst_address = ut.institute.address
        return room

    async def soft_delete(self, room_id: int) -> bool:
        room = await self.session.get(Room, room_id)
        if not room or room.deleted_at is not None:
            return False
        room.deleted_at = datetime.utcnow()
        room.status = RoomStatus.offline
        await self.session.commit()
        await self._audit("删除房间", room.id, {"房号": room.room_number, "楼层": room.floor})
        return True

    async def restore(self, room_id: int) -> Room | None:
        # 第一步：找到已删除房间并恢复
        room = await self.session.get(Room, room_id)
        if not room or room.deleted_at is None:
            return None
        room.deleted_at = None
        room.status = RoomStatus.available
        await self.session.commit()
        await self._audit("恢复房间", room.id, {"房号": room.room_number})
        # 第二步：重新用 eager load 查询，commit 后所有属性已 expire，
        #         必须重新加载关联以免 _to_read 触发 MissingGreenlet
        from app.models.unit_type import UnitType
        stmt = (
            select(Room)
            .options(
                selectinload(Room.images),
                selectinload(Room.unit_type).selectinload(UnitType.institute),
            )
            .where(Room.id == room_id)
        )
        result = await self.session.scalars(stmt)
        return result.unique().first()

    async def hard_delete(self, room_id: int) -> bool:
        room = await self.session.get(Room, room_id)
        if not room:
            return False
        await self.session.delete(room)
        await self.session.commit()
        return True

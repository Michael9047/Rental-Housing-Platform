"""房间服务层"""
import uuid as _uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.property import Room, RoomStatus
from app.models.unit_type import UnitType
from app.schemas.room import RoomCreate, RoomUpdate


class RoomService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _audit(self, action: str, resource_id: int, details: dict | None = None):
        try:
            log = AuditLog(action=action, resource_type="room", resource_id=resource_id, details=details)
            self.session.add(log)
            await self.session.commit()
        except Exception:
            pass

    async def create(self, data: RoomCreate) -> Room:
        from app.core.business_id import generate_business_id
        biz_id = await generate_business_id(self.session, "room")
        room = Room(
            uuid=str(_uuid.uuid4()),
            business_id=biz_id,
            landlord_id=data.landlord_id,
            unit_type_id=data.unit_type_id,
            room_number=data.room_number,
            building_block=data.building_block,
            floor=data.floor,
            special_discount=data.special_discount,
            available_from=data.available_from,
            min_stay_months=data.min_stay_months,
            status=data.status if isinstance(data.status, RoomStatus) else RoomStatus(data.status),
        )
        self.session.add(room)
        await self.session.commit()

        ut = await self.session.get(UnitType, room.unit_type_id, options=[selectinload(UnitType.institute)])
        ut_name = ut.name if ut else ''
        inst_name = ut.institute.name if ut and ut.institute else ''
        desc = f"在「{inst_name}」公寓的「{ut_name}」户型下创建了房间「{room.room_number}」"
        if room.floor is not None: desc += f"，位于第{room.floor}层"
        await self._audit("创建房间", room.id, {"描述": desc, "房号": room.room_number, "楼层": room.floor, "公寓": inst_name, "户型": ut_name})

        # 预加载关联
        ut = await self.session.get(UnitType, room.unit_type_id, options=[selectinload(UnitType.institute)])
        if ut:
            room._ut_name = ut.name; room._ut_base_rent = ut.base_rent
            room._ut_area_sqm = ut.area_sqm; room._ut_bedrooms = ut.bedrooms
            room._ut_bathrooms = ut.bathrooms; room._ut_hall_count = ut.hall_count
            room._ut_deposit_amount = ut.deposit_amount; room._ut_amenities = ut.amenities
            if ut.institute:
                room._inst_name = ut.institute.name; room._inst_address = ut.institute.address
        return room

    async def get(self, room_id: int) -> Room | None:
        stmt = (select(Room)
                .options(selectinload(Room.unit_type).selectinload(UnitType.institute), selectinload(Room.images))
                .where(Room.id == room_id))
        result = await self.session.scalars(stmt)
        return result.unique().first()

    async def check_duplicate(self, unit_type_id: int, room_number: str, exclude_id: int | None = None) -> bool:
        from sqlalchemy import and_
        filters = [Room.unit_type_id == unit_type_id, Room.room_number == room_number, Room.deleted_at.is_(None)]
        if exclude_id: filters.append(Room.id != exclude_id)
        count = (await self.session.scalar(select(func.count(Room.id)).where(and_(*filters)))) or 0
        return count > 0

    async def list(self, *, skip: int = 0, limit: int = 20, unit_type_id: int | None = None, institute_id: int | None = None, landlord_id: int | None = None, status: str | None = None, include_deleted: bool = False) -> dict:
        filters = []
        if not include_deleted: filters.append(Room.deleted_at.is_(None))
        if unit_type_id is not None: filters.append(Room.unit_type_id == unit_type_id)
        if landlord_id is not None: filters.append(Room.landlord_id == landlord_id)
        if status: filters.append(Room.status == status)

        base = select(func.count(Room.id))
        if institute_id is not None:
            base = base.join(UnitType, Room.unit_type_id == UnitType.id)
            filters.append(UnitType.institute_id == institute_id)
        for f in filters: base = base.where(f)
        total = (await self.session.scalar(base)) or 0

        stmt = (select(Room)
                .options(selectinload(Room.images), selectinload(Room.unit_type).selectinload(UnitType.institute))
                .order_by(Room.created_at.desc()).offset(skip).limit(limit))
        if institute_id is not None:
            stmt = stmt.join(UnitType, Room.unit_type_id == UnitType.id)
        for f in filters: stmt = stmt.where(f)

        result = await self.session.scalars(stmt)
        items = list(result.unique())
        return {"items": items, "total": total, "page": skip // limit + 1, "page_size": limit, "total_pages": max(1, (total + limit - 1) // limit)}

    async def update(self, room_id: int, data: RoomUpdate) -> Room | None:
        room = await self.get(room_id)
        if not room: return None
        if data.version is not None and data.version != room.version:
            from fastapi import HTTPException
            raise HTTPException(409, "数据已被他人修改，请刷新后重试")
        update_data = data.model_dump(exclude_unset=True, exclude={"version"})
        old_vals = {k: str(getattr(room, k, '')) for k in update_data}
        for k, v in update_data.items():
            if k == 'status' and not isinstance(v, RoomStatus):
                v = RoomStatus(v)
            setattr(room, k, v)
        room.version += 1
        await self.session.commit()
        await self.session.refresh(room)

        desc_parts = []
        for k, v in update_data.items():
            old_val = old_vals.get(k, '')
            cn_map = {'room_number': '房号', 'floor': '楼层', 'special_discount': '专属优惠', 'available_from': '可入住日期', 'status': '状态'}
            desc_parts.append(f"{cn_map.get(k, k)}从「{old_val}」改为「{v}」")
        await self._audit("编辑房间", room.id, {"描述": "；".join(desc_parts), "房号": room.room_number, "修改内容": {k: {"新值": str(v), "旧值": old_vals.get(k, '')} for k, v in update_data.items()}})

        ut = await self.session.get(UnitType, room.unit_type_id, options=[selectinload(UnitType.institute)])
        if ut:
            room._ut_name = ut.name; room._ut_base_rent = ut.base_rent
            room._ut_area_sqm = ut.area_sqm; room._ut_bedrooms = ut.bedrooms
            room._ut_bathrooms = ut.bathrooms; room._ut_hall_count = ut.hall_count
            room._ut_deposit_amount = ut.deposit_amount; room._ut_amenities = ut.amenities
            if ut.institute:
                room._inst_name = ut.institute.name; room._inst_address = ut.institute.address
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
        room = await self.session.get(Room, room_id)
        if not room or room.deleted_at is None:
            return None
        room.deleted_at = None
        room.status = RoomStatus.available
        await self.session.commit()
        await self._audit("恢复房间", room.id, {"房号": room.room_number})
        stmt = (select(Room)
                .options(selectinload(Room.images), selectinload(Room.unit_type).selectinload(UnitType.institute))
                .where(Room.id == room_id))
        result = await self.session.scalars(stmt)
        return result.unique().first()

    async def hard_delete(self, room_id: int) -> bool:
        room = await self.session.get(Room, room_id)
        if not room: return False
        await self.session.delete(room)
        await self.session.commit()
        return True

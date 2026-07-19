"""房型业务逻辑"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.models.room_type import RoomType
from app.schemas.room_type import RoomTypeCreate, RoomTypeUpdate

logger = logging.getLogger(__name__)


class RoomTypeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_property(self, property_id: int) -> list[RoomType]:
        result = await self.session.execute(
            select(RoomType)
            .where(RoomType.property_id == property_id)
            .order_by(RoomType.price_monthly.asc())
        )
        return list(result.scalars().all())

    async def get(self, property_id: int, room_type_id: int) -> RoomType | None:
        result = await self.session.execute(
            select(RoomType).where(
                RoomType.id == room_type_id,
                RoomType.property_id == property_id,
            )
        )
        return result.scalars().first()

    async def create(self, property_id: int, data: RoomTypeCreate, user_id: int) -> RoomType:
        # 校验楼栋存在
        prop = await self.session.get(Property, property_id)
        if not prop:
            raise ValueError("楼栋不存在")

        rt = RoomType(property_id=property_id, **data.model_dump())
        self.session.add(rt)
        await self.session.commit()
        await self.session.refresh(rt)
        return rt

    async def update(self, property_id: int, room_type_id: int, data: RoomTypeUpdate, user_id: int) -> RoomType | None:
        rt = await self.get(property_id, room_type_id)
        if not rt:
            return None

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(rt, key, value)
        rt.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(rt)
        return rt

    async def delete(self, property_id: int, room_type_id: int, user_id: int) -> bool:
        rt = await self.get(property_id, room_type_id)
        if not rt:
            return False
        await self.session.delete(rt)
        await self.session.commit()
        return True

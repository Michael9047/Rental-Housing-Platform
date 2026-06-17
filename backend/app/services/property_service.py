from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyUpdate


class PropertyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, property_in: PropertyCreate) -> Property:
        property_obj = Property(**property_in.model_dump())
        self.session.add(property_obj)
        await self.session.commit()
        await self.session.refresh(property_obj)
        return property_obj

    async def get(self, property_id: int) -> Property | None:
        return await self.session.get(Property, property_id)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        district: str | None = None,
        status: str | None = None,
    ) -> list[Property]:
        stmt = select(Property).order_by(Property.created_at.desc()).offset(skip).limit(limit)
        if district:
            stmt = stmt.where(Property.district == district)
        if status:
            stmt = stmt.where(Property.status == status)
        result = await self.session.scalars(stmt)
        return list(result)

    async def update(self, property_id: int, property_in: PropertyUpdate) -> Property | None:
        property_obj = await self.get(property_id)
        if not property_obj:
            return None

        for key, value in property_in.model_dump(exclude_unset=True).items():
            setattr(property_obj, key, value)

        await self.session.commit()
        await self.session.refresh(property_obj)
        return property_obj

    async def delete(self, property_id: int) -> bool:
        property_obj = await self.get(property_id)
        if not property_obj:
            return False

        await self.session.delete(property_obj)
        await self.session.commit()
        return True

from __future__ import annotations

import logging
import threading
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyUpdate

logger = logging.getLogger(__name__)


class PropertyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, property_in: PropertyCreate) -> Property:
        property_obj = Property(**property_in.model_dump())
        self.session.add(property_obj)
        await self.session.commit()
        await self.session.refresh(property_obj)

        self._dispatch_embedding_task(property_obj.id)
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

    async def search(
        self,
        *,
        query: str | None = None,
        district: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        limit: int = 20,
    ) -> list[tuple[Property, float | None]]:
        if query:
            from app.services.embedding_service import EmbeddingService
            from pgvector.sqlalchemy import l2_distance

            embedding_service = EmbeddingService()
            query_vec = await embedding_service.generate_embedding(query)

            similarity_expr = l2_distance(Property.embedding, query_vec).label("similarity")
            stmt = (
                select(Property, similarity_expr)
                .where(Property.embedding.isnot(None))
            )
            stmt = stmt.order_by(similarity_expr)
        else:
            stmt = (
                select(Property, text("NULL AS similarity"))
            )
            stmt = stmt.order_by(Property.created_at.desc())

        if district:
            stmt = stmt.where(Property.district == district)
        if price_min is not None:
            stmt = stmt.where(Property.price_monthly >= price_min)
        if price_max is not None:
            stmt = stmt.where(Property.price_monthly <= price_max)
        if bedrooms is not None:
            stmt = stmt.where(Property.bedrooms == bedrooms)
        if property_type:
            stmt = stmt.where(Property.property_type == property_type)

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()
        return [(row[0], row[1]) for row in rows]

    async def update(self, property_id: int, property_in: PropertyUpdate) -> Property | None:
        property_obj = await self.get(property_id)
        if not property_obj:
            return None

        for key, value in property_in.model_dump(exclude_unset=True).items():
            setattr(property_obj, key, value)

        await self.session.commit()
        await self.session.refresh(property_obj)

        self._dispatch_embedding_task(property_obj.id)
        return property_obj

    async def delete(self, property_id: int) -> bool:
        property_obj = await self.get(property_id)
        if not property_obj:
            return False

        await self.session.delete(property_obj)
        await self.session.commit()
        return True

    @staticmethod
    def _dispatch_embedding_task(property_id: int) -> None:
        def _run() -> None:
            try:
                from app.tasks.embedding_tasks import generate_property_embedding

                generate_property_embedding.delay(property_id)
            except Exception:
                logger.exception(
                    "Failed to dispatch embedding task for property %s", property_id
                )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
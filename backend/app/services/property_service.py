from __future__ import annotations

import json
import logging
import threading
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyUpdate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis cache helpers (lazy import to avoid hard dependency at module level)
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 300  # 5 minutes for search results


def _cache_key(prefix: str, **kwargs: Any) -> str:
    """Build a deterministic cache key from search parameters."""
    raw = json.dumps(kwargs, sort_keys=True, default=str)
    return f"search:{prefix}:{raw}"


async def _get_redis() -> "Redis | None":  # noqa: F821
    """Return an async Redis client if available."""
    try:
        from redis.asyncio import Redis as AsyncRedis

        from app.core.config import get_settings

        return AsyncRedis.from_url(get_settings().redis_url, decode_responses=False)
    except Exception:
        logger.debug("Redis not available; search caching disabled.")
        return None


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
        # --- Cache check for non-vector searches (cacheable) ---
        if not query:
            cache_params = {
                "district": district,
                "price_min": str(price_min) if price_min else None,
                "price_max": str(price_max) if price_max else None,
                "bedrooms": bedrooms,
                "property_type": property_type,
                "limit": limit,
            }
            cache_key_str = _cache_key("filter", **cache_params)
            redis = await _get_redis()
            if redis is not None:
                try:
                    cached = await redis.get(cache_key_str)
                    if cached:
                        logger.debug("Search cache hit for key=%s", cache_key_str)
                        rows_data = json.loads(cached)
                        await redis.aclose()
                        return [
                            (Property(**row["property"]), row["similarity"])
                            for row in rows_data
                        ]
                except Exception:
                    logger.debug("Cache retrieval failed, proceeding without cache.")
                finally:
                    if redis is not None:
                        try:
                            await redis.aclose()
                        except Exception:
                            pass

        # --- Build query ---
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
        results = [(row[0], row[1]) for row in rows]

        # --- Cache non-vector results ---
        if not query:
            redis = await _get_redis()
            if redis is not None:
                try:
                    rows_data = [
                        {
                            "property": {
                                k: (str(v) if isinstance(v, Decimal) else v)
                                for k, v in row[0].__dict__.items()
                                if not k.startswith("_")
                            },
                            "similarity": row[1],
                        }
                        for row in rows
                    ]
                    await redis.setex(cache_key_str, CACHE_TTL_SECONDS, json.dumps(rows_data, default=str))
                except Exception:
                    logger.debug("Cache write failed, continuing.")
                finally:
                    try:
                        await redis.aclose()
                    except Exception:
                        pass

        return results

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

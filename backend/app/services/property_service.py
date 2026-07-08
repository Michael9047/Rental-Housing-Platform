from __future__ import annotations

import json
import logging
import threading
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.services.poi_service import POIService
from app.schemas.property import PropertyCreate, PropertyUpdate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis cache helpers (lazy import to avoid hard dependency at module level)
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 300  # 5 minutes for search results
SEARCH_CACHE_VERSION_KEY = "search:cache_version"


def _cache_key(prefix: str, version: str, **kwargs: Any) -> str:
    """Build a deterministic, version-scoped cache key from search parameters.

    The version prefix lets us invalidate the whole search cache namespace in
    one atomic INCR (see ``_bump_search_cache_version``) whenever a property is
    created/updated/deleted, instead of scanning and deleting individual keys.
    """
    raw = json.dumps(kwargs, sort_keys=True, default=str)
    return f"search:{prefix}:v{version}:{raw}"


async def _get_redis() -> "Redis | None":  # noqa: F821
    """Return an async Redis client if available."""
    try:
        from redis.asyncio import Redis as AsyncRedis

        from app.core.config import get_settings

        return AsyncRedis.from_url(get_settings().redis_url, decode_responses=False)
    except Exception:
        logger.debug("Redis not available; search caching disabled.")
        return None


async def _get_cache_version(redis) -> str:
    """Read the current search cache version (defaults to "0")."""
    value = await redis.get(SEARCH_CACHE_VERSION_KEY)
    if value is None:
        return "0"
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


async def _bump_search_cache_version() -> None:
    """Invalidate all cached search results by bumping the namespace version.

    Old keys become unreachable immediately and expire on their own via TTL.
    No-op when Redis is unavailable.
    """
    redis = await _get_redis()
    if redis is None:
        return
    try:
        await redis.incr(SEARCH_CACHE_VERSION_KEY)
    except Exception:
        logger.debug("Failed to bump search cache version.")
    finally:
        try:
            await redis.aclose()
        except Exception:
            pass


class PropertyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, property_in: PropertyCreate) -> Property:
        property_obj = Property(**property_in.model_dump())
        self.session.add(property_obj)
        await self.session.commit()
        await self.session.refresh(property_obj)

        try:
            await POIService(self.session).generate_poi_for_property(property_obj)
        except Exception:
            logger.exception("Failed to generate POI for property %s", property_obj.id)

        await self._ensure_embedding(property_obj)
        await _bump_search_cache_version()
        return property_obj

    async def get(self, property_id: int) -> Property | None:
        property_obj = await self.session.get(Property, property_id)
        if property_obj is not None:
            # Preload POI data
            from sqlalchemy import select as sa_select
            from app.models.poi import PropertyPOI
            stmt = sa_select(PropertyPOI).where(PropertyPOI.property_id == property_id)
            result = await self.session.execute(stmt)
            poi = result.scalars().first()
            if poi:
                property_obj.poi = poi
        return property_obj

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
        status: str | None = None,
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
                "status": status,
                "limit": limit,
            }
            redis = await _get_redis()
            if redis is not None:
                try:
                    version = await _get_cache_version(redis)
                    cache_key_str = _cache_key("filter", version, **cache_params)
                    cached = await redis.get(cache_key_str)
                    if cached:
                        logger.debug("Search cache hit for key=%s", cache_key_str)
                        rows_data = json.loads(cached)
                        return [
                            (Property(**row["property"]), row["similarity"])
                            for row in rows_data
                        ]
                except Exception:
                    logger.debug("Cache retrieval failed, proceeding without cache.")
                finally:
                    try:
                        await redis.aclose()
                    except Exception:
                        pass

        # --- Build query ---
        if query:
            from sqlalchemy import Float

            from app.services.embedding_service import EmbeddingService

            embedding_service = EmbeddingService()
            query_vec = await embedding_service.generate_embedding(query)

            # pgvector 的 L2 距离操作符（新版 pgvector 不再导出 l2_distance 函数）
            similarity_expr = (
                Property.embedding.op("<->", return_type=Float)(query_vec).label("similarity")
            )
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
        if status:
            stmt = stmt.where(Property.status == status)

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()
        results = [(row[0], row[1]) for row in rows]

        # --- Cache non-vector results ---
        if not query:
            redis = await _get_redis()
            if redis is not None:
                try:
                    version = await _get_cache_version(redis)
                    cache_key_str = _cache_key("filter", version, **cache_params)
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

        try:
            await POIService(self.session).generate_poi_for_property(property_obj, force=True)
        except Exception:
            logger.exception("Failed to refresh POI for property %s", property_obj.id)

        await self._ensure_embedding(property_obj)
        await _bump_search_cache_version()
        return property_obj

    async def delete(self, property_id: int) -> bool:
        property_obj = await self.get(property_id)
        if not property_obj:
            return False

        await self.session.delete(property_obj)
        await self.session.commit()
        await _bump_search_cache_version()
        return True

    async def _ensure_embedding(self, property_obj: Property) -> None:
        """Make the property searchable via semantic search.

        Sync-first: when an embedding provider (Zhipu or OpenAI) is configured,
        generate the embedding inline and commit it *before returning*, so the
        property is immediately found by AI/semantic search (which filters on
        ``embedding IS NOT NULL``). On any failure — or when no key is
        configured — fall back to the async Celery task so the upload itself
        is never blocked or coupled to the embedding API's availability.
        """
        from app.services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService()
        if embedding_service.is_available:
            try:
                property_type = (
                    property_obj.property_type.value
                    if hasattr(property_obj.property_type, "value")
                    else str(property_obj.property_type)
                )
                embedding = await embedding_service.generate_property_embedding(
                    {
                        "title": property_obj.title,
                        "description": property_obj.description,
                        "address": property_obj.address,
                        "district": property_obj.district,
                        "property_type": property_type,
                    }
                )
                property_obj.embedding = embedding
                await self.session.commit()
                # commit 使 ORM 属性过期；刷新后再交给响应序列化，
                # 否则访问 updated_at 等字段会在异步上下文外触发懒加载报错
                await self.session.refresh(property_obj)
                return
            except Exception:
                logger.exception(
                    "Sync embedding failed for property %s, falling back to async task",
                    property_obj.id,
                )

        # Fallback (also the default path when no provider is configured)
        self._dispatch_embedding_task(property_obj.id)

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

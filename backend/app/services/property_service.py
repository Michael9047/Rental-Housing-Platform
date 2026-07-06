from __future__ import annotations

import json
import logging
import threading
import uuid
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
        dumped = property_in.model_dump()
        image_urls = dumped.pop("image_urls", None) or []
        logger.info("Creating property: institute_id=%s, keys=%s", dumped.get('institute_id'), list(dumped.keys()))

        # AI风险评估
        from app.services.risk_evaluator import RiskEvaluator
        evaluator = RiskEvaluator()
        risk = evaluator.evaluate_single(dumped)
        if risk.should_set_pending:
            dumped["status"] = "pending_review"
            logger.info("Property flagged for review: %s", risk.warnings)

        property_obj = Property(**dumped)
        self.session.add(property_obj)
        await self.session.commit()
        await self.session.refresh(property_obj)

        # 绑定临时上传的图片到房源
        if image_urls:
            await self._attach_temp_images(property_obj.id, image_urls)
            # 刷新对象以加载刚创建的 images 关系
            await self.session.refresh(property_obj, attribute_names=['images'])

        # Eager-load institute and set institute_name
        if property_obj.institute_id:
            from sqlalchemy.orm import selectinload
            from app.models.institute import Institute
            stmt = select(Property).where(Property.id == property_obj.id).options(selectinload(Property.institute))
            result = await self.session.execute(stmt)
            loaded = result.scalars().first()
            if loaded and loaded.institute:
                object.__setattr__(property_obj, 'institute_name', loaded.institute.name)

        try:
            await POIService(self.session).generate_poi_for_property(property_obj)
        except Exception:
            logger.exception("Failed to generate POI for property %s", property_obj.id)

        self._dispatch_embedding_task(property_obj.id)
        return property_obj

    async def get(self, property_id: int) -> Property | None:
        from sqlalchemy.orm import selectinload
        from app.models.poi import PropertyPOI
        stmt = select(Property).where(Property.id == property_id).options(selectinload(Property.institute))
        result = await self.session.execute(stmt)
        property_obj = result.scalars().first()
        if property_obj is not None:
            if property_obj.institute:
                object.__setattr__(property_obj, 'institute_name', property_obj.institute.name)
            poi_result = await self.session.execute(
                select(PropertyPOI).where(PropertyPOI.property_id == property_id)
            )
            poi = poi_result.scalars().first()
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
        landlord_id: int | None = None,
        keyword: str | None = None,
        property_type: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> list[Property]:
        from sqlalchemy.orm import selectinload
        from sqlalchemy import or_

        stmt = (select(Property)
                .options(selectinload(Property.institute))
                .order_by(Property.created_at.desc())
                .offset(skip).limit(limit))
        if district:
            stmt = stmt.where(Property.district == district)
        if status:
            stmt = stmt.where(Property.status == status)
        elif landlord_id is None:
            stmt = stmt.where(Property.status == "available")
        if landlord_id is not None:
            stmt = stmt.where(Property.landlord_id == landlord_id)
        # 关键词模糊搜索：房号/标题/地址
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            stmt = stmt.where(or_(
                Property.room_number.ilike(kw),
                Property.title.ilike(kw),
                Property.address.ilike(kw),
            ))
        if property_type:
            stmt = stmt.where(Property.property_type == property_type)
        if price_min is not None:
            stmt = stmt.where(Property.price_monthly >= price_min)
        if price_max is not None:
            stmt = stmt.where(Property.price_monthly <= price_max)

        result = await self.session.scalars(stmt)
        properties = list(result)
        for p in properties:
            if p.institute and p.institute.name:
                object.__setattr__(p, 'institute_name', p.institute.name)
        return properties

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
        # --- Build query ---
        from sqlalchemy.orm import selectinload

        if query:
            from app.services.embedding_service import EmbeddingService
            from pgvector.sqlalchemy import l2_distance

            embedding_service = EmbeddingService()
            query_vec = await embedding_service.generate_embedding(query)

            similarity_expr = l2_distance(Property.embedding, query_vec).label("similarity")
            stmt = (
                select(Property, similarity_expr)
                .options(selectinload(Property.institute))
                .where(Property.embedding.isnot(None))
            )
            stmt = stmt.order_by(similarity_expr)
        else:
            stmt = (
                select(Property, text("NULL AS similarity"))
                .options(selectinload(Property.institute))
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

        # 公开搜索：只展示可租房源
        stmt = stmt.where(Property.status == "available")

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()
        results = [(row[0], row[1]) for row in rows]

        # 注入 institute_name（与 list() 方法保持一致）
        for prop, _sim in results:
            if prop.institute and prop.institute.name:
                object.__setattr__(prop, 'institute_name', prop.institute.name)

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

        self._dispatch_embedding_task(property_obj.id)
        return property_obj

    async def delete(self, property_id: int) -> bool:
        property_obj = await self.get(property_id)
        if not property_obj:
            return False

        await self.session.delete(property_obj)
        await self.session.commit()
        return True

    async def _attach_temp_images(self, property_id: int, urls: list[str]) -> None:
        """将临时上传的图片绑定到房源，移动文件并创建 PropertyImage 记录。"""
        import shutil
        from pathlib import Path

        from app.core.config import get_settings
        from app.models.property_image import PropertyImage

        settings = get_settings()
        upload_dir = Path(settings.upload_dir).resolve()
        prop_dir = upload_dir / "properties" / str(property_id)
        prop_dir.mkdir(parents=True, exist_ok=True)

        for sort_order, url in enumerate(urls):
            # URL 格式: /api/v1/uploads/temp/{user_id}/{filename} 或 /api/v1/uploads/temp/batch/{user_id}/{filename}
            relative = url.replace("/api/v1/uploads/", "")
            src = upload_dir / relative
            if not src.exists():
                continue

            ext = src.suffix
            new_name = f"{uuid.uuid4().hex}{ext}"
            dst = prop_dir / new_name
            shutil.move(str(src), str(dst))

            img = PropertyImage(
                property_id=property_id,
                filename=f"properties/{property_id}/{new_name}",
                original_name=src.name,
                mime_type="image/" + ext.lstrip(".") if ext.lstrip(".") in ("jpeg", "jpg", "png", "webp") else "image/jpeg",
                file_size=dst.stat().st_size,
                sort_order=sort_order,
                is_primary=(sort_order == 0),
            )
            self.session.add(img)
        await self.session.commit()

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

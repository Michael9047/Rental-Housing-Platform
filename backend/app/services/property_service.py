from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import VALID_STATUS_TRANSITIONS, Property, PropertyStatus
from app.services.poi_service import POIService
from app.schemas.property import PropertyCreate, PropertyUpdate

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300


def _cache_key(prefix: str, **kwargs: Any) -> str:
    raw = json.dumps(kwargs, sort_keys=True, default=str)
    return f"search:{prefix}:{raw}"


async def _get_redis() -> "Redis | None":  # noqa: F821
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
            await self.session.refresh(property_obj, attribute_names=['images'])

        # Eager-load institute
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

        # 审计日志
        await self._audit(property_obj.landlord_id, "property_create", property_obj.id,
                          {"title": property_obj.title, "district": property_obj.district})

        return property_obj

    async def get(self, property_id: int) -> Property | None:
        from sqlalchemy.orm import selectinload
        from app.models.poi import PropertyPOI
        stmt = (select(Property)
                .where(Property.id == property_id, Property.deleted_at.is_(None))
                .options(selectinload(Property.institute)))
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
        include_deleted: bool = False,
    ) -> dict:
        """返回分页结果: {items, total, page, page_size, total_pages}"""
        from sqlalchemy.orm import selectinload
        from sqlalchemy import or_

        base = select(func.count(Property.id))
        base = base.where(Property.deleted_at.is_(None) if not include_deleted else True)

        if district:
            base = base.where(Property.district == district)
        if status:
            base = base.where(Property.status == status)
        elif landlord_id is None and not include_deleted:
            base = base.where(Property.status == "available")
        if landlord_id is not None:
            base = base.where(Property.landlord_id == landlord_id)
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            base = base.where(or_(
                Property.room_number.ilike(kw),
                Property.title.ilike(kw),
                Property.address.ilike(kw),
            ))
        if property_type:
            base = base.where(Property.property_type == property_type)
        if price_min is not None:
            base = base.where(Property.price_monthly >= price_min)
        if price_max is not None:
            base = base.where(Property.price_monthly <= price_max)

        total_result = await self.session.scalar(base)
        total = total_result or 0

        stmt = (
            select(Property)
            .options(selectinload(Property.institute))
            .where(Property.deleted_at.is_(None) if not include_deleted else True)
            .order_by(Property.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if district:
            stmt = stmt.where(Property.district == district)
        if status:
            stmt = stmt.where(Property.status == status)
        elif landlord_id is None and not include_deleted:
            stmt = stmt.where(Property.status == "available")
        if landlord_id is not None:
            stmt = stmt.where(Property.landlord_id == landlord_id)
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

        page = (skip // limit) + 1 if limit > 0 else 1
        return {
            "items": properties,
            "total": total,
            "page": page,
            "page_size": limit,
            "total_pages": max(1, (total + limit - 1) // limit) if limit > 0 else 1,
        }

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
                .where(Property.embedding.isnot(None), Property.deleted_at.is_(None))
            )
            stmt = stmt.order_by(similarity_expr)
        else:
            stmt = (
                select(Property, text("NULL AS similarity"))
                .options(selectinload(Property.institute))
                .where(Property.deleted_at.is_(None))
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

        stmt = stmt.where(Property.status == "available")
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()
        results = [(row[0], row[1]) for row in rows]

        for prop, _sim in results:
            if prop.institute and prop.institute.name:
                object.__setattr__(prop, 'institute_name', prop.institute.name)

        return results

    async def update(self, property_id: int, property_in: PropertyUpdate) -> Property | None:
        property_obj = await self.get(property_id)
        if not property_obj:
            return None

        # 乐观锁：校验版本号
        if property_in.version is not None:
            if property_in.version != property_obj.version:
                raise ValueError("数据已被他人修改，请刷新页面后重试")

        # 状态机校验
        new_status = property_in.status
        if new_status is not None:
            current = PropertyStatus(property_obj.status) if isinstance(property_obj.status, str) else property_obj.status
            target = PropertyStatus(new_status) if isinstance(new_status, str) else new_status
            allowed = VALID_STATUS_TRANSITIONS.get(current, set())
            if target not in allowed and target != current:
                raise ValueError(
                    f"不允许从「{current.value}」直接切换为「{target.value}」。"
                    f"允许的流转: {[s.value for s in allowed]}"
                )

        update_data = property_in.model_dump(exclude_unset=True)
        # version 由服务端自增，不从客户端取值
        update_data.pop("version", None)

        for key, value in update_data.items():
            setattr(property_obj, key, value)

        # 自动递增版本号
        property_obj.version = (property_obj.version or 0) + 1
        property_obj.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(property_obj)

        try:
            await POIService(self.session).generate_poi_for_property(property_obj, force=True)
        except Exception:
            logger.exception("Failed to refresh POI for property %s", property_obj.id)

        self._dispatch_embedding_task(property_obj.id)

        await self._audit(property_obj.landlord_id, "property_update", property_obj.id,
                          {"title": property_obj.title, "changed_fields": list(update_data.keys())})

        return property_obj

    async def delete(self, property_id: int) -> bool:
        """软删除：设置 deleted_at"""
        property_obj = await self.get(property_id)
        if not property_obj:
            return False

        property_obj.deleted_at = datetime.now(timezone.utc)
        property_obj.status = PropertyStatus.offline
        await self.session.commit()

        await self._audit(property_obj.landlord_id, "property_delete", property_obj.id,
                          {"title": property_obj.title})
        return True

    async def restore(self, property_id: int) -> Property | None:
        """从回收站恢复"""
        from sqlalchemy.orm import selectinload
        stmt = select(Property).where(Property.id == property_id, Property.deleted_at.isnot(None))
        result = await self.session.execute(stmt)
        property_obj = result.scalars().first()
        if not property_obj:
            return None

        property_obj.deleted_at = None
        property_obj.status = PropertyStatus.available
        await self.session.commit()
        await self.session.refresh(property_obj)
        return property_obj

    async def batch_update_status(self, ids: list[int], new_status: str, landlord_id: int) -> dict:
        """批量更新状态（事务性）"""
        from app.models.property import PropertyStatus as PS
        target = PS(new_status)
        updated = 0
        errors = []

        for pid in ids:
            try:
                prop = await self.get(pid)
                if not prop:
                    errors.append({"id": pid, "error": "房源不存在"})
                    continue
                current = PS(prop.status) if isinstance(prop.status, str) else prop.status
                allowed = VALID_STATUS_TRANSITIONS.get(current, set())
                if target not in allowed and target != current:
                    errors.append({"id": pid, "error": f"不允许从 {current.value} → {target.value}"})
                    continue
                prop.status = target
                prop.version = (prop.version or 0) + 1
                prop.updated_at = datetime.now(timezone.utc)
                updated += 1
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})

        if errors and updated == 0:
            # 全部失败，回滚
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        await self.session.commit()
        await self._audit(landlord_id, "property_batch_status", 0,
                          {"ids": ids, "new_status": new_status, "updated": updated})
        return {"success": updated, "failed": len(errors), "errors": errors}

    async def batch_delete(self, ids: list[int], landlord_id: int) -> dict:
        """批量软删除"""
        now = datetime.now(timezone.utc)
        deleted = 0
        for pid in ids:
            prop = await self.get(pid)
            if prop:
                prop.deleted_at = now
                prop.status = PropertyStatus.offline
                deleted += 1
        await self.session.commit()
        await self._audit(landlord_id, "property_batch_delete", 0, {"ids": ids, "deleted": deleted})
        return {"success": deleted, "failed": len(ids) - deleted}

    async def hard_delete(self, property_id: int) -> bool:
        """物理删除：从数据库彻底移除（回收站专用）"""
        from sqlalchemy.orm import selectinload
        stmt = select(Property).where(Property.id == property_id, Property.deleted_at.isnot(None))
        result = await self.session.execute(stmt)
        property_obj = result.scalars().first()
        if not property_obj:
            return False
        await self.session.delete(property_obj)
        await self.session.commit()
        await self._audit(property_obj.landlord_id, 'property_hard_delete', property_obj.id,
                          {'title': property_obj.title})
        return True

    async def batch_restore(self, ids: list[int], landlord_id: int) -> dict:
        """批量恢复"""
        restored = 0
        for pid in ids:
            try:
                prop = await self.restore(pid)
                if prop:
                    restored += 1
            except Exception:
                pass
        await self._audit(landlord_id, 'property_batch_restore', 0, {'ids': ids, 'restored': restored})
        return {'success': restored, 'failed': len(ids) - restored}

    async def batch_hard_delete(self, ids: list[int], landlord_id: int) -> dict:
        """批量物理删除"""
        deleted = 0
        for pid in ids:
            if await self.hard_delete(pid):
                deleted += 1
        await self._audit(landlord_id, 'property_batch_hard_delete', 0, {'ids': ids, 'deleted': deleted})
        return {'success': deleted, 'failed': len(ids) - deleted}

    async def _attach_temp_images(self, property_id: int, urls: list[str]) -> None:
        import shutil
        from pathlib import Path
        from app.core.config import get_settings
        from app.models.property_image import PropertyImage

        settings = get_settings()
        upload_dir = Path(settings.upload_dir).resolve()
        prop_dir = upload_dir / "properties" / str(property_id)
        prop_dir.mkdir(parents=True, exist_ok=True)

        for sort_order, url in enumerate(urls):
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
                logger.exception("Failed to dispatch embedding task for property %s", property_id)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    async def _audit(self, user_id: int, action: str, resource_id: int, details: dict) -> None:
        try:
            from app.services.audit_service import AuditService
            await AuditService(self.session).create_log(
                user_id=user_id,
                action=action,
                resource_type="property",
                resource_id=resource_id,
                details=details,
            )
        except Exception:
            logger.exception("Failed to write audit log for action=%s", action)

"""房源服务 — UnitType 搜索与 CRUD（两层架构：Institute → UnitType）

Phase 3 重写：基于 UnitType + Institute JOIN，所有查询走新模型。
保持 PropertyService 类名与导入路径不变，供旧调用方兼容过渡。
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.unit_type import UnitType, UnitTypeStatus, PropertyType, DepositType
from app.models.institute import Institute, InstituteStatus
from app.schemas.property import PropertyCreate, PropertyUpdate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis 缓存辅助（保留兼容，可选）
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 300
SEARCH_CACHE_VERSION_KEY = "search:cache_version"


def _cache_key(prefix: str, version: str, **kwargs: Any) -> str:
    """构建版本作用域的缓存 key。"""
    raw = json.dumps(kwargs, sort_keys=True, default=str)
    return f"search:{prefix}:v{version}:{raw}"


async def _get_redis() -> "Redis | None":  # noqa: F821
    try:
        from redis.asyncio import Redis as AsyncRedis
        from app.core.config import get_settings
        return AsyncRedis.from_url(get_settings().redis_url, decode_responses=False)
    except Exception:
        logger.debug("Redis not available; search caching disabled.")
        return None


async def _get_cache_version(redis) -> str:
    value = await redis.get(SEARCH_CACHE_VERSION_KEY)
    if value is None:
        return "0"
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


async def _bump_search_cache_version() -> None:
    """递增缓存版本号，使旧缓存 key 不可达。"""
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


# ---------------------------------------------------------------------------
# 房型类型映射（旧值 → 新 PropertyType 枚举值）
# ---------------------------------------------------------------------------

_ROOM_TYPE_TO_PROPERTY_TYPE: dict[str, str] = {
    "one_bed": "1bed",
    "two_bed": "2bed",
    "three_bed_plus": "3bed",
    "four_bed": "4bed",
    "five_bed_plus": "5bed+",
}


def _resolve_property_type(type_value: str | None) -> str | None:
    """将可能的旧房型值映射为新 PropertyType 枚举值。"""
    if not type_value:
        return None
    return _ROOM_TYPE_TO_PROPERTY_TYPE.get(type_value, type_value)


# ---------------------------------------------------------------------------
# PropertyService
# ---------------------------------------------------------------------------


class PropertyService:
    """UnitType 房源搜索与 CRUD 服务。

    所有查询以 UnitType 为主表，JOIN Institute 获取公寓信息。
    方法签名与旧 PropertyService 保持最大兼容。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── search ──────────────────────────────────────────────────────────

    async def search(  # noqa: C901
        self,
        *,
        query: str | None = None,
        q: str | None = None,
        district: str | None = None,
        country: str | None = None,
        city: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        bedrooms: int | None = None,
        bathrooms: int | None = None,
        property_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
        institute_id: int | None = None,
        room_type: str | None = None,
        amenities: list[str] | None = None,
        available_from: str | None = None,
        min_lease_months: int | None = None,
        max_lease_months: int | None = None,
        area_min: float | None = None,
        area_max: float | None = None,
        sort_by: str | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        near_distance_km: float | None = None,
        female_only: bool | None = None,
    ) -> list[tuple[UnitType, float | None]]:
        """UnitType + Institute JOIN 搜索。

        返回 list of (UnitType, similarity) — similarity 始终为 None（向量检索后续添加）。
        """
        # 统一 query/q 参数
        search_text = q or query

        # 尝试缓存（非文本搜索可缓存）
        if not search_text:
            cache_params = {
                "district": district, "country": country, "city": city,
                "price_min": str(price_min) if price_min else None,
                "price_max": str(price_max) if price_max else None,
                "bedrooms": bedrooms, "bathrooms": bathrooms,
                "property_type": property_type, "status": status,
                "limit": limit, "institute_id": institute_id,
                "room_type": room_type,
                "amenities": sorted(amenities) if amenities else None,
                "available_from": available_from,
                "min_lease_months": min_lease_months,
                "max_lease_months": max_lease_months,
                "area_min": area_min, "area_max": area_max,
                "sort_by": sort_by,
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
                        # 缓存只存了 JSON 快照，无法重建 ORM 对象 —— 跳过缓存返回空
                        # （后续可改为缓存序列化数据，当前直接查库保证正确性）
                except Exception:
                    logger.debug("Cache retrieval failed, proceeding without cache.")
                finally:
                    try:
                        await redis.aclose()
                    except Exception:
                        pass

        # 构建基础查询：UnitType JOIN Institute
        stmt = (
            select(UnitType, text("NULL AS similarity"))
            .join(Institute, UnitType.institute_id == Institute.id)
            .where(UnitType.deleted_at.is_(None))
            .options(selectinload(UnitType.institute))
        )

        # ── 文本搜索 ──
        if search_text:
            kw = f"%{search_text.strip()}%"
            stmt = stmt.where(
                or_(
                    UnitType.name.ilike(kw),
                    Institute.name.ilike(kw),
                    UnitType.description.ilike(kw),
                )
            )

        # ── 地区筛选（Institute 侧）──
        if district:
            stmt = stmt.where(Institute.district.ilike(f"%{district}%"))
        if country:
            stmt = stmt.where(Institute.country == country)
        if city:
            stmt = stmt.where(Institute.city.ilike(f"%{city}%"))

        # ── 价格筛选（UnitType 侧）──
        if price_min is not None:
            stmt = stmt.where(UnitType.base_rent >= price_min)
        if price_max is not None:
            stmt = stmt.where(UnitType.base_rent <= price_max)

        # ── 户型筛选 ──
        if bedrooms is not None:
            stmt = stmt.where(UnitType.bedrooms == bedrooms)
        if bathrooms is not None:
            stmt = stmt.where(UnitType.bathrooms >= bathrooms)

        # ── 类型筛选 ──
        resolved_type = _resolve_property_type(property_type or room_type)
        if resolved_type:
            stmt = stmt.where(UnitType.property_type == resolved_type)

        # ── 状态筛选 ──
        if status:
            stmt = stmt.where(UnitType.status == status)
        else:
            stmt = stmt.where(UnitType.status == UnitTypeStatus.available.value)

        # ── 公寓筛选 ──
        if institute_id is not None:
            stmt = stmt.where(UnitType.institute_id == institute_id)

        # ── 设施筛选（ARRAY 重叠）──
        if amenities:
            stmt = stmt.where(UnitType.amenities.op("&&")(amenities))

        # ── 面积筛选 ──
        if area_min is not None:
            stmt = stmt.where(UnitType.area_sqm >= area_min)
        if area_max is not None:
            stmt = stmt.where(UnitType.area_sqm <= area_max)

        # ── 入住时间 ──
        if available_from:
            year = int(available_from[:4])
            month = int(available_from[4:6])
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            stmt = stmt.where(
                UnitType.available_from.isnot(None),
                UnitType.available_from < end_date,
            )

        # ── 租期筛选 ──
        if min_lease_months is not None:
            stmt = stmt.where(UnitType.min_stay_months >= min_lease_months)
        # max_lease_months: UnitType 只有 min_stay_months，忽略此条件（已无 max_lease 字段）

        # ── 大学距离 bounding box ──
        if near_lat is not None and near_lng is not None and near_distance_km is not None:
            import math as _math
            lat_d = near_distance_km / 111.0
            lng_d = near_distance_km / (111.0 * _math.cos(_math.radians(near_lat)))
            stmt = stmt.where(
                Institute.latitude >= near_lat - lat_d,
                Institute.latitude <= near_lat + lat_d,
                Institute.longitude >= near_lng - lng_d,
                Institute.longitude <= near_lng + lng_d,
            )

        # ── 其他 Institute 筛选 ──
        if female_only is not None:
            stmt = stmt.where(Institute.female_only == female_only)
        if max_lease_months is not None:
            pass  # UnitType 无此字段

        # ── 排序 ──
        if sort_by == "price_asc":
            stmt = stmt.order_by(UnitType.base_rent.asc())
        elif sort_by == "price_desc":
            stmt = stmt.order_by(UnitType.base_rent.desc())
        elif sort_by == "created_at":
            stmt = stmt.order_by(UnitType.created_at.desc())
        else:
            stmt = stmt.order_by(UnitType.created_at.desc())

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()
        results: list[tuple[UnitType, float | None]] = [(row[0], row[1]) for row in rows]

        # ── 写入缓存 ──
        if not search_text:
            redis = await _get_redis()
            if redis is not None:
                try:
                    version = await _get_cache_version(redis)
                    cache_key_str = _cache_key("filter", version, **cache_params)
                    rows_data = [
                        {
                            "unit_type_id": row[0].id,
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

    # ── search_unit_types ───────────────────────────────────────────────

    async def search_unit_types(
        self,
        *,
        district: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        near_distance_km: float | None = None,
        female_only: bool | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """搜户型 — UnitType + Institute JOIN，不再聚合 Room。

        返回 [{"unit_type": UnitType, "institute": Institute, "available_rooms": int, "min_price": Decimal, "embedding": str}, ...]
        """
        stmt = (
            select(UnitType, Institute)
            .join(Institute, UnitType.institute_id == Institute.id)
            .where(
                UnitType.status == UnitTypeStatus.available,
                Institute.status == InstituteStatus.active,
                UnitType.deleted_at.is_(None),
            )
            .options(selectinload(UnitType.institute))
        )

        if district:
            stmt = stmt.where(Institute.district.ilike(f"%{district}%"))
        if price_min is not None:
            stmt = stmt.where(UnitType.base_rent >= price_min)
        if price_max is not None:
            stmt = stmt.where(UnitType.base_rent <= price_max)
        if bedrooms is not None:
            stmt = stmt.where(UnitType.bedrooms == bedrooms)
        if property_type:
            stmt = stmt.where(UnitType.property_type == _resolve_property_type(property_type))
        if female_only is not None:
            stmt = stmt.where(Institute.female_only == female_only)

        if near_lat is not None and near_lng is not None and near_distance_km is not None:
            import math as _math
            lat_d = near_distance_km / 111.0
            lng_d = near_distance_km / (111.0 * _math.cos(_math.radians(near_lat)))
            stmt = stmt.where(
                Institute.latitude >= near_lat - lat_d,
                Institute.latitude <= near_lat + lat_d,
                Institute.longitude >= near_lng - lng_d,
                Institute.longitude <= near_lng + lng_d,
            )

        stmt = stmt.order_by(UnitType.base_rent.asc()).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            {
                "unit_type": row[0],
                "institute": row[1],
                "available_rooms": row[0].available_count,
                "min_price": row[0].base_rent,
                "embedding": row[0].embedding,
            }
            for row in rows
        ]

    # ── list ────────────────────────────────────────────────────────────

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        institute_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
        property_type: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        include_deleted: bool = False,
        **kwargs: Any,
    ) -> dict:
        """分页列出 UnitType，支持基本筛选。

        返回 {"items": [UnitType], "total": int, "page": int, "page_size": int, "total_pages": int}
        """
        clauses: list = []

        if not include_deleted:
            clauses.append(UnitType.deleted_at.is_(None))

        if institute_id is not None:
            clauses.append(UnitType.institute_id == institute_id)
        if status:
            clauses.append(UnitType.status == status)
        if property_type:
            clauses.append(UnitType.property_type == _resolve_property_type(property_type))
        if price_min is not None:
            clauses.append(UnitType.base_rent >= price_min)
        if price_max is not None:
            clauses.append(UnitType.base_rent <= price_max)
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            clauses.append(
                or_(
                    UnitType.name.ilike(kw),
                    UnitType.description.ilike(kw),
                )
            )

        # Count
        base = select(func.count(UnitType.id))
        for clause in clauses:
            base = base.where(clause)
        total_result = await self.session.scalar(base)
        total = total_result or 0

        # Data
        stmt = (
            select(UnitType)
            .options(selectinload(UnitType.institute))
            .order_by(UnitType.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        for clause in clauses:
            stmt = stmt.where(clause)

        result = await self.session.scalars(stmt)
        items = list(result)

        page = (skip // limit) + 1 if limit > 0 else 1
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": limit,
            "total_pages": max(1, (total + limit - 1) // limit) if limit > 0 else 1,
        }

    # ── get ─────────────────────────────────────────────────────────────

    async def get(self, unit_type_id: int) -> UnitType | None:
        """获取单个 UnitType，eager-load institute。"""
        stmt = (
            select(UnitType)
            .where(UnitType.id == unit_type_id, UnitType.deleted_at.is_(None))
            .options(selectinload(UnitType.institute))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # ── create ──────────────────────────────────────────────────────────

    async def create(self, property_in: PropertyCreate) -> UnitType:
        """从 PropertyCreate schema 创建 UnitType。

        注意：schema 中的旧字段名会透传（PropertyCreate 设置了 extra="allow"），
        方法内部将其映射到 UnitType 字段。
        """
        data = property_in.model_dump(exclude_unset=False)

        # 字段映射：旧名 → 新名
        _field_map = {
            "title": "name",
            "price_monthly": "base_rent",
        }
        for old_key, new_key in _field_map.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)

        # 清理 UnitType 不认识的字段
        _allowed_unit_type_keys = {
            "institute_id", "name", "property_type", "bedrooms", "bathrooms",
            "hall_count", "area_sqm", "base_rent", "deposit_amount", "deposit_type",
            "lease_start", "lease_end", "currency", "special_offer",
            "floor_pricing", "total_count", "available_count", "has_vacancy",
            "amenities", "image_urls", "description", "available_from",
            "min_stay_months", "status",
        }
        filtered = {k: v for k, v in data.items() if k in _allowed_unit_type_keys}

        # 确保必填字段
        if "name" not in filtered or not filtered["name"]:
            filtered["name"] = data.get("title") or "未命名户型"
        if "base_rent" not in filtered:
            filtered["base_rent"] = Decimal("0")

        unit_type = UnitType(**filtered)
        self.session.add(unit_type)
        await self.session.commit()
        await self.session.refresh(unit_type)

        await _bump_search_cache_version()

        await self._audit(
            0,  # user_id 由调用方覆盖
            "unit_type_create",
            unit_type.id,
            {"name": unit_type.name, "institute_id": unit_type.institute_id},
        )

        return unit_type

    # ── update ──────────────────────────────────────────────────────────

    async def update(self, unit_type_id: int, property_in: PropertyUpdate) -> UnitType | None:
        """更新 UnitType。"""
        unit_type = await self.get(unit_type_id)
        if not unit_type:
            return None

        # 乐观锁
        if property_in.version is not None:
            current_version = getattr(unit_type, "version", None)
            if current_version is not None and property_in.version != current_version:
                raise ValueError("数据已被他人修改，请刷新页面后重试")

        update_data = property_in.model_dump(exclude_unset=True)
        update_data.pop("version", None)

        # 字段名映射
        if "price_monthly" in update_data:
            update_data["base_rent"] = update_data.pop("price_monthly")
        if "title" in update_data:
            update_data["name"] = update_data.pop("title")

        # 状态机校验（如果提供 status）
        new_status = update_data.get("status")
        if new_status is not None:
            try:
                target = UnitTypeStatus(new_status)
            except ValueError:
                raise ValueError(f"无效的状态值: {new_status}")
            # UnitType 状态允许任意转换（简化版）

        old_values = {}
        for key in list(update_data.keys()):
            if hasattr(unit_type, key):
                old_val = getattr(unit_type, key)
                if hasattr(old_val, 'value'):
                    old_val = old_val.value
                elif hasattr(old_val, 'isoformat'):
                    old_val = old_val.isoformat()
                elif isinstance(old_val, Decimal):
                    old_val = str(old_val)
                old_values[key] = old_val
                setattr(unit_type, key, update_data[key])
            else:
                update_data.pop(key, None)

        unit_type.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(unit_type)

        await _bump_search_cache_version()

        await self._audit(
            0, "unit_type_update", unit_type.id,
            {
                "name": unit_type.name,
                "changed_fields": list(old_values.keys()),
                "old_values": old_values,
            },
        )

        return unit_type

    # ── delete / restore / hard_delete ──────────────────────────────────

    async def delete(self, unit_type_id: int) -> bool:
        """软删除 UnitType。"""
        unit_type = await self.get(unit_type_id)
        if not unit_type:
            return False

        unit_type.deleted_at = datetime.now(timezone.utc)
        unit_type.status = UnitTypeStatus.maintenance
        await self.session.commit()

        await self._audit(0, "unit_type_delete", unit_type.id, {"name": unit_type.name})
        return True

    async def restore(self, unit_type_id: int) -> UnitType | None:
        """恢复已删除的 UnitType。"""
        stmt = (
            select(UnitType)
            .where(UnitType.id == unit_type_id, UnitType.deleted_at.isnot(None))
            .options(selectinload(UnitType.institute))
        )
        result = await self.session.execute(stmt)
        unit_type = result.scalars().first()
        if not unit_type:
            return None

        unit_type.deleted_at = None
        unit_type.status = UnitTypeStatus.available
        await self.session.commit()
        await self.session.refresh(unit_type)

        await self._audit(0, "unit_type_restore", unit_type.id, {"name": unit_type.name})
        return unit_type

    async def hard_delete(self, unit_type_id: int) -> bool:
        """物理删除 UnitType（回收站专用）。"""
        stmt = (
            select(UnitType)
            .where(UnitType.id == unit_type_id, UnitType.deleted_at.isnot(None))
            .options(selectinload(UnitType.institute))
        )
        result = await self.session.execute(stmt)
        unit_type = result.scalars().first()
        if not unit_type:
            return False

        institute_name = unit_type.institute.name if unit_type.institute else None
        await self.session.delete(unit_type)
        await self.session.commit()

        await _bump_search_cache_version()
        await self._audit(0, "unit_type_hard_delete", unit_type_id,
                          {"name": unit_type.name, "institute_name": institute_name})
        return True

    # ── 批量操作 ────────────────────────────────────────────────────────

    async def batch_update_status(
        self, ids: list[int], new_status: str, landlord_id: int
    ) -> dict:
        """批量更新 UnitType 状态。"""
        try:
            target = UnitTypeStatus(new_status)
        except ValueError:
            return {"success": 0, "failed": len(ids), "errors": [{"id": None, "error": f"无效状态: {new_status}"}]}

        updated = 0
        errors: list[dict] = []

        for pid in ids:
            try:
                ut = await self.get(pid)
                if not ut:
                    errors.append({"id": pid, "error": "户型不存在"})
                    continue
                ut.status = target
                ut.updated_at = datetime.now(timezone.utc)
                updated += 1
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})

        if errors and updated == 0:
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        await self.session.commit()
        await self._audit(landlord_id, "unit_type_batch_status", 0,
                          {"ids": ids, "new_status": new_status, "updated": updated})
        return {"success": updated, "failed": len(errors), "errors": errors}

    async def batch_delete(self, ids: list[int], landlord_id: int) -> dict:
        """批量软删除 UnitType。"""
        now = datetime.now(timezone.utc)
        deleted = 0
        errors: list[dict] = []
        snapshots: list[dict] = []

        for pid in ids:
            try:
                ut = await self.get(pid)
                if ut:
                    snapshots.append({"id": ut.id, "name": ut.name})
                    ut.deleted_at = now
                    ut.status = UnitTypeStatus.maintenance
                    deleted += 1
                else:
                    errors.append({"id": pid, "error": "户型不存在"})
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})

        if errors and deleted == 0:
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        try:
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            errors.append({"id": None, "error": f"批量提交失败：{e}"})
            return {"success": 0, "failed": len(ids), "errors": errors}

        await self._audit(landlord_id, "unit_type_batch_delete", 0,
                          {"ids": ids, "deleted": deleted, "snapshots": snapshots})
        return {"success": deleted, "failed": len(errors), "errors": errors}

    async def batch_restore(self, ids: list[int], landlord_id: int) -> dict:
        """批量恢复 UnitType。"""
        restored = 0
        errors: list[dict] = []
        snapshots: list[dict] = []

        for pid in ids:
            try:
                stmt = (
                    select(UnitType)
                    .where(UnitType.id == pid, UnitType.deleted_at.isnot(None))
                    .options(selectinload(UnitType.institute))
                )
                result = await self.session.execute(stmt)
                ut = result.scalars().first()
                if ut:
                    snapshots.append({
                        "id": ut.id, "name": ut.name,
                        "institute_name": ut.institute.name if ut.institute else None,
                    })
                    ut.deleted_at = None
                    ut.status = UnitTypeStatus.available
                    restored += 1
                else:
                    errors.append({"id": pid, "error": "户型不存在或未被删除"})
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})

        if errors and restored == 0:
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        try:
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            errors.append({"id": None, "error": f"批量提交失败：{e}"})
            return {"success": 0, "failed": len(ids), "errors": errors}

        try:
            await self._audit(landlord_id, "unit_type_batch_restore", 0,
                              {"ids": ids, "restored": restored, "snapshots": snapshots})
        except Exception:
            logger.exception("Audit log write failed for batch_restore")

        return {"success": restored, "failed": len(errors), "errors": errors}

    async def batch_hard_delete(self, ids: list[int], landlord_id: int) -> dict:
        """批量物理删除 UnitType。"""
        deleted = 0
        errors: list[dict] = []
        snapshots: list[dict] = []

        for pid in ids:
            try:
                stmt = (
                    select(UnitType)
                    .where(UnitType.id == pid, UnitType.deleted_at.isnot(None))
                    .options(selectinload(UnitType.institute))
                )
                result = await self.session.execute(stmt)
                ut = result.scalars().first()
                if ut:
                    snapshots.append({
                        "id": ut.id, "name": ut.name,
                        "institute_name": ut.institute.name if ut.institute else None,
                    })
                    await self.session.delete(ut)
                    deleted += 1
                else:
                    errors.append({"id": pid, "error": "户型不存在或未被删除"})
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})

        if errors and deleted == 0:
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        try:
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            errors.append({"id": None, "error": f"批量提交失败：{e}"})
            return {"success": 0, "failed": len(ids), "errors": errors}

        await _bump_search_cache_version()
        try:
            await self._audit(landlord_id, "unit_type_batch_hard_delete", 0,
                              {"ids": ids, "deleted": deleted, "snapshots": snapshots})
        except Exception:
            logger.exception("Audit log write failed for batch_hard_delete")

        return {"success": deleted, "failed": len(errors), "errors": errors}

    # ── audit ───────────────────────────────────────────────────────────

    async def get_recent_audit(self, landlord_id: int, *, limit: int = 20) -> list[dict]:
        """获取最近的 UnitType 审计日志。"""
        from app.models.audit_log import AuditLog

        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type.in_(["unit_type", "property"]),
                AuditLog.user_id == landlord_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        logs = list(result)

        return [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    async def _audit(
        self, user_id: int, action: str, resource_id: int, details: dict
    ) -> bool:
        """写入审计日志，不阻塞主流程。"""
        try:
            from app.services.audit_service import AuditService
            await AuditService(self.session).create_log(
                user_id=user_id,
                action=action,
                resource_type="property",
                resource_id=resource_id,
                details=details,
            )
            return True
        except Exception:
            logger.exception("Failed to write audit log for action=%s", action)
            import sys
            print(
                f"\n[!] 审计日志写入失败！操作={action}, ID={resource_id}, 用户ID={user_id}",
                file=sys.stderr,
            )
            return False

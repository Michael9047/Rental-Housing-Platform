from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import cast, func, or_, select, String, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import VALID_STATUS_TRANSITIONS, DepositType, Property, PropertyStatus, PropertyType
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

    @staticmethod
    def _legacy_read_options(*, existing_columns: set[str] | None = None) -> tuple:
        """只读取旧库真实存在的房源列，按实际表结构补充兼容字段。"""
        from sqlalchemy.orm import load_only, selectinload

        property_columns = [
            Property.id,
            Property.landlord_id,
            Property.room_number,
            Property.institute_id,
            Property.title,
            Property.address,
            Property.district,
            Property.price_monthly,
            Property.area_sqm,
            Property.bedrooms,
            Property.bathrooms,
            Property.property_type,
            Property.deposit_amount,
            Property.deposit_type,
            Property.service_fee_rate,
            Property.description,
            Property.country,
            Property.latitude,
            Property.longitude,
            Property.rent_type,
            Property.rental_rules,
            Property.amenities,
            Property.embedding,
            Property.floor,
            Property.available_from,
            Property.status,
            Property.min_stay_months,
            Property.min_lease_months,
            Property.max_lease_months,
            Property.version,
            Property.deleted_at,
            Property.created_at,
            Property.updated_at,
        ]
        optional_columns = {
            "unit_type_id": Property.unit_type_id,
            "institute_name": Property.institute_name,
            "institute_amenities": Property.institute_amenities,
            "female_only": Property.female_only,
            "safety_score": Property.safety_score,
            "currency": Property.currency,
            "building_block": Property.building_block,
            "special_discount": Property.special_discount,
            "city": Property.city,
        }
        for column_name, attribute in optional_columns.items():
            if existing_columns and column_name in existing_columns:
                property_columns.append(attribute)

        return (
            load_only(*property_columns),
            selectinload(Property.images),
        )

    @staticmethod
    def _apply_legacy_defaults(property_obj: Property) -> Property:
        """为旧库缺失的新字段填只读默认值，禁止触发延迟查列。"""
        from sqlalchemy.orm.attributes import set_committed_value

        amenities = list(getattr(property_obj, "amenities", None) or [])
        defaults = {
            "unit_type_id": None,
            "institute_name": None,
            "institute_amenities": json.dumps(amenities, ensure_ascii=False),
            "female_only": False,
            "safety_score": None,
            "currency": "CNY",
            "building_block": None,
            "special_discount": None,
            "city": property_obj.district,
        }
        for field_name, value in defaults.items():
            if field_name not in property_obj.__dict__:
                set_committed_value(property_obj, field_name, value)
        return property_obj

    @staticmethod
    def _normalize_room_write_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """把兼容接口字段映射到当前房间表，避免旧字段直接传给 ORM。"""
        normalized = dict(payload)
        amenities = normalized.pop("amenities", None)
        special_offer = normalized.pop("special_offer", None)

        if amenities is not None:
            normalized["institute_amenities"] = json.dumps(
                amenities,
                ensure_ascii=False,
            )
        if special_offer is not None:
            normalized["special_discount"] = str(special_offer)

        column_names = set(Property.__table__.columns.keys())
        unsupported = sorted(set(normalized) - column_names)
        if unsupported:
            logger.warning("忽略房间模型不支持的写入字段: %s", unsupported)
        return {
            key: value
            for key, value in normalized.items()
            if key in column_names
        }

    async def create(self, property_in: PropertyCreate) -> Property:
        dumped = property_in.model_dump()
        image_urls = dumped.pop("image_urls", None) or []
        dumped = self._normalize_room_write_payload(dumped)
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

        # 异步派发 Google Maps 全量 POI 检索（不阻塞创建流程）
        try:
            from app.tasks.poi_tasks import generate_full_poi_for_property
            generate_full_poi_for_property.delay(property_obj.id)
        except Exception:
            logger.exception("Failed to dispatch POI task for property %s", property_obj.id)

        await self._ensure_embedding(property_obj)
        await _bump_search_cache_version()

        # 审计日志
        await self._audit(property_obj.landlord_id, "property_create", property_obj.id,
                          {"title": property_obj.title, "district": property_obj.district,
                           "property_title": property_obj.title,
                           "property_address": property_obj.address,
                           "institute_name": getattr(property_obj, "institute_name", None)})

        # 审计写入会提交同一会话；返回前刷新标量字段，避免异步响应序列化触发懒加载。
        await self.session.refresh(property_obj)

        return property_obj

    async def get(self, property_id: int) -> Property | None:
        from app.models.poi import PropertyPOI
        from sqlalchemy.orm import load_only
        stmt = (select(Property)
                .where(Property.id == property_id, Property.deleted_at.is_(None))
                .options(*self._legacy_read_options()))
        result = await self.session.execute(stmt)
        property_obj = result.scalars().first()
        if property_obj is not None:
            self._apply_legacy_defaults(property_obj)
            poi_result = await self.session.execute(
                select(PropertyPOI)
                .options(load_only(
                    PropertyPOI.id,
                    PropertyPOI.property_id,
                    PropertyPOI.content,
                    PropertyPOI.poi_data,
                    PropertyPOI.generated_at,
                    PropertyPOI.reviewed,
                    PropertyPOI.map_poi_data,
                    PropertyPOI.created_at,
                    PropertyPOI.updated_at,
                ))
                .where(PropertyPOI.property_id == property_id)
            )
            poi = poi_result.scalars().first()
            if poi:
                property_obj.poi = poi
        return property_obj

    def _build_filters(
        self,
        *,
        district: str | None = None,
        country: str | None = None,
        status: str | None = None,
        landlord_id: int | None = None,
        keyword: str | None = None,
        property_type: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        institute_id: int | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        near_distance_km: float | None = None,
        include_deleted: bool = False,
    ) -> list:
        """构建公共 WHERE 条件列表，供 list() 的 count 和 data 查询复用。"""
        from sqlalchemy import or_
        clauses = []

        if not include_deleted:
            clauses.append(Property.deleted_at.is_(None))

        if district:
            clauses.append(Property.district.ilike(f"%{district}%"))
        if country:
            clauses.append(Property.country.ilike(f"%{country}%"))
        if near_lat is not None and near_lng is not None and near_distance_km is not None:
            # Bounding box 近似预筛选（~111km/度纬度, ~111*cos(lat)km/度经度）
            import math
            lat_delta = near_distance_km / 111.0
            lng_delta = near_distance_km / (111.0 * math.cos(math.radians(near_lat)))
            clauses.append(Property.latitude >= near_lat - lat_delta)
            clauses.append(Property.latitude <= near_lat + lat_delta)
            clauses.append(Property.longitude >= near_lng - lng_delta)
            clauses.append(Property.longitude <= near_lng + lng_delta)
        if status:
            clauses.append(cast(Property.status, String) == status)
        elif landlord_id is None and not include_deleted:
            clauses.append(cast(Property.status, String) == "available")
        if landlord_id is not None:
            clauses.append(Property.landlord_id == landlord_id)
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            clauses.append(or_(
                Property.room_number.ilike(kw),
                Property.title.ilike(kw),
                Property.address.ilike(kw),
            ))
        if property_type:
            clauses.append(cast(Property.property_type, String) == property_type)
        if price_min is not None:
            clauses.append(Property.price_monthly >= price_min)
        if price_max is not None:
            clauses.append(Property.price_monthly <= price_max)
        if institute_id is not None:
            clauses.append(Property.institute_id == institute_id)

        return clauses

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        district: str | None = None,
        country: str | None = None,
        status: str | None = None,
        landlord_id: int | None = None,
        keyword: str | None = None,
        property_type: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        institute_id: int | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        near_distance_km: float | None = None,
        include_deleted: bool = False,
    ) -> dict:
        """返回分页结果: {items, total, page, page_size, total_pages}"""
        filter_clauses = self._build_filters(
            district=district, country=country, status=status, landlord_id=landlord_id,
            keyword=keyword, property_type=property_type,
            price_min=price_min, price_max=price_max,
            institute_id=institute_id,
            near_lat=near_lat, near_lng=near_lng, near_distance_km=near_distance_km,
            include_deleted=include_deleted,
        )

        # Count query
        base = select(func.count(Property.id))
        for clause in filter_clauses:
            base = base.where(clause)
        total_result = await self.session.scalar(base)
        total = total_result or 0

        # Data query
        stmt = (
            select(Property)
            .options(*self._legacy_read_options())
            .order_by(Property.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        for clause in filter_clauses:
            stmt = stmt.where(clause)

        result = await self.session.scalars(stmt)
        properties = [self._apply_legacy_defaults(item) for item in result]

        page = (skip // limit) + 1 if limit > 0 else 1
        return {
            "items": properties,
            "total": total,
            "page": page,
            "page_size": limit,
            "total_pages": max(1, (total + limit - 1) // limit) if limit > 0 else 1,
        }

    @staticmethod
    def _room_type_filter_clause(room_type: str):
        """按三层模型中的户型表生成房型条件。"""
        from app.models.unit_type import UnitType

        normalized = str(room_type).strip().lower().replace("_", "-")
        if normalized in {"studio", "单间", "开间"}:
            unit_type_clause = or_(
                UnitType.bedrooms == 0,
                UnitType.name.ilike("%studio%"),
                UnitType.name.ilike("%单间%"),
                UnitType.name.ilike("%开间%"),
            )
        elif normalized in {"ensuite", "独卫"}:
            unit_type_clause = or_(
                UnitType.name.ilike("%ensuite%"),
                UnitType.name.ilike("%独卫%"),
                UnitType.name.ilike("%独立卫浴%"),
            )
        elif normalized in {"1bed", "1-bed", "one-bed"}:
            unit_type_clause = UnitType.bedrooms == 1
        elif normalized in {"2bed", "2-bed", "two-bed"}:
            unit_type_clause = UnitType.bedrooms == 2
        elif normalized in {"3bed+", "3-bed+", "three-bed-plus"}:
            unit_type_clause = UnitType.bedrooms >= 3
        elif normalized in {"shared", "合租"}:
            unit_type_clause = or_(
                UnitType.name.ilike("%shared%"),
                UnitType.name.ilike("%合租%"),
                UnitType.name.ilike("%床位%"),
            )
        else:
            unit_type_clause = UnitType.name.ilike(f"%{normalized}%")

        unit_type_ids = select(UnitType.id).where(unit_type_clause)
        return Property.unit_type_id.in_(unit_type_ids)

    async def search_unit_types(
        self,
        *,
        district: str | None = None,
        country: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        near_distance_km: float | None = None,
        female_only: bool | None = None,
        query_vec: list[float] | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """搜户型 —— 搜索主表为 unit_types，JOIN institutes，聚合 rooms 库存。

        embedding 在 unit_types 上，P0 条件分布在 institutes + unit_types。
        当传入 query_vec 时，语义相似度排序由数据库 pgvector 完成
        （ORDER BY embedding <=> query_vec），不再把向量拉回应用层用 numpy 全量计算。
        返回 [{unit_type, institute, available_rooms, min_price, embedding_score}, ...]
        embedding_score ∈ [0,1]（无向量/该行未生成 embedding 时为 None）。
        """
        from sqlalchemy import inspect
        connection = await self.session.connection()
        has_unit_types = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).has_table("unit_types")
        )
        if not has_unit_types:
            return []

        from sqlalchemy.orm import defer
        from sqlalchemy.orm.attributes import set_committed_value
        from app.models.unit_type import UnitType, UnitTypeStatus
        from app.models.institute import Institute, InstituteStatus
        from app.models.property import Room, RoomStatus

        available_count_expr = func.count(Room.id).filter(
            Room.status == RoomStatus.available.value
        )
        representative_property_expr = func.min(Room.id).filter(
            Room.status == RoomStatus.available.value
        )
        min_available_price_expr = func.min(Room.price_monthly).filter(
            Room.status == RoomStatus.available.value
        )
        select_cols = [
            UnitType,
            Institute,
            available_count_expr.label("available_rooms"),
            min_available_price_expr.label("min_price"),
            representative_property_expr.label("representative_property_id"),
        ]
        # 语义排序下推 DB：cosine 距离与 HNSW(vector_cosine_ops) 索引一致
        distance_expr = None
        if query_vec is not None:
            distance_expr = UnitType.embedding.cosine_distance(query_vec)
            select_cols.append(distance_expr.label("distance"))

        stmt = (
            select(*select_cols)
            # 不把 1536 维向量本身传回应用层（最多 limit 行，避免十几 MB 传输）
            .options(defer(UnitType.embedding))
            .join(Institute, UnitType.institute_id == Institute.id)
            .outerjoin(Room, Room.unit_type_id == UnitType.id)
            .where(
                cast(UnitType.status, String) == UnitTypeStatus.available.value,
                cast(Institute.status, String) == InstituteStatus.active.value,
                UnitType.deleted_at.is_(None),
            )
        )

        if district:
            district_pattern = f"%{district}%"
            stmt = stmt.where(or_(
                Institute.district.ilike(district_pattern),
                Institute.city.ilike(district_pattern),
                Institute.country.ilike(district_pattern),
                Institute.name.ilike(district_pattern),
                Institute.name_cn.ilike(district_pattern),
            ))
        if country:
            normalized_country = str(country).strip()
            country_aliases = {
                "CN": ("CN", "China", "中国"),
                "SG": ("SG", "Singapore", "新加坡"),
                "GB": ("GB", "UK", "United Kingdom", "英国"),
                "UK": ("GB", "UK", "United Kingdom", "英国"),
                "US": ("US", "USA", "United States", "美国"),
                "HK": ("HK", "Hong Kong", "香港"),
            }.get(normalized_country.upper(), (normalized_country,))
            stmt = stmt.where(or_(
                *(Institute.country.ilike(f"%{alias}%") for alias in country_aliases)
            ))
        if price_min is not None:
            stmt = stmt.where(UnitType.base_rent >= price_min)
        if price_max is not None:
            stmt = stmt.where(UnitType.base_rent <= price_max)
        if bedrooms is not None:
            stmt = stmt.where(UnitType.bedrooms == bedrooms)
        if property_type:
            room_type = str(property_type).lower().replace("_", "-")
            if room_type == "studio":
                stmt = stmt.where(or_(
                    UnitType.bedrooms == 0,
                    UnitType.name.ilike("%studio%"),
                    UnitType.name.ilike("%单间%"),
                    UnitType.name.ilike("%开间%"),
                ))
            elif room_type in {"1-bed", "1bed", "one-bed"}:
                stmt = stmt.where(UnitType.bedrooms == 1)
            elif room_type in {"2-bed", "2bed", "two-bed"}:
                stmt = stmt.where(UnitType.bedrooms == 2)
            elif room_type in {"3-bed+", "3bed+", "three-bed-plus"}:
                stmt = stmt.where(UnitType.bedrooms >= 3)
            elif room_type in {"shared", "合租"}:
                stmt = stmt.where(or_(
                    UnitType.name.ilike("%shared%"),
                    UnitType.name.ilike("%合租%"),
                    UnitType.name.ilike("%床位%"),
                ))
        if female_only is not None:
            stmt = stmt.where(Institute.female_only == female_only)
        # 大学距离 bounding box
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

        # 排序：有查询向量时按语义距离升序（最相似在前）；否则按租金升序
        stmt = stmt.group_by(UnitType.id, Institute.id).having(available_count_expr > 0)
        if distance_expr is not None:
            stmt = stmt.order_by(distance_expr.asc().nullslast(), UnitType.base_rent.asc()).limit(limit)
        else:
            stmt = stmt.order_by(UnitType.base_rent.asc()).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()
        items: list[dict] = []
        for row in rows:
            unit_type, institute = row[0], row[1]
            # 查询已 JOIN 出 Institute，显式绑定避免响应序列化时触发异步 lazy-load。
            set_committed_value(unit_type, "institute", institute)
            items.append({
                "unit_type": unit_type,
                "institute": institute,
                "available_rooms": row[2],
                "min_price": row[3] or unit_type.base_rent,
                "_unit_type_id": int(unit_type.id),
                "_property_id": int(row[4]),
                "_source_kind": "unit_type",
                # cosine 距离 ∈ [0,2] → 相似度 ∈ [0,1]（1-距离，clamp 到非负）
                "embedding_score": (
                    max(0.0, 1.0 - float(row[5])) if row[5] is not None else None
                ) if distance_expr is not None else None,
            })
        return items

    async def search(
        self,
        *,
        query: str | None = None,
        district: str | None = None,
        country: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
        institute_id: int | None = None,
        room_type: str | None = None,
        amenities: list[str] | None = None,
        available_from: str | None = None,
        min_lease_months: int | None = None,
        max_lease_months: int | None = None,
        bathrooms: int | None = None,
        area_min: float | None = None,
        area_max: float | None = None,
        sort_by: str | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        near_distance_km: float | None = None,
        female_only: bool | None = None,
    ) -> list[tuple[Property, float | None]]:
        # --- Cache check for non-vector searches (cacheable) ---
        if not query:
            cache_params = {
                "district": district,
                "country": country,
                "price_min": str(price_min) if price_min else None,
                "price_max": str(price_max) if price_max else None,
                "bedrooms": bedrooms,
                "property_type": property_type,
                "status": status,
                "limit": limit,
                "institute_id": institute_id,
                "room_type": room_type,
                "amenities": sorted(amenities) if amenities else None,
                "available_from": available_from,
                "min_lease_months": min_lease_months,
                "max_lease_months": max_lease_months,
                "bathrooms": bathrooms,
                "area_min": area_min,
                "area_max": area_max,
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

        query_vec = None
        if query:
            from app.services.embedding_service import get_embedding_service

            embedding_service = get_embedding_service()
            try:
                query_vec = await embedding_service.generate_embedding(query)
            except Exception:
                logger.warning("Embedding failed for query '%s', falling back to keyword", query)

            if query_vec is not None:
                # cosine 距离，与 HNSW(vector_cosine_ops) 索引一致
                similarity_expr = Property.embedding.cosine_distance(query_vec).label("similarity")
                stmt = (
                    select(Property, similarity_expr)
                    .options(*self._legacy_read_options())
                    .where(Property.embedding.isnot(None), Property.deleted_at.is_(None))
                )
                stmt = stmt.order_by(similarity_expr)
            else:
                query_vec = None  # 确保走关键词回退
                stmt = (
                    select(Property, text("NULL AS similarity"))
                    .options(*self._legacy_read_options())
                    .where(Property.deleted_at.is_(None))
                )
                stmt = stmt.order_by(Property.created_at.desc())
        else:
            stmt = (
                select(Property, text("NULL AS similarity"))
                .options(*self._legacy_read_options())
                .where(Property.deleted_at.is_(None))
            )
            stmt = stmt.order_by(Property.created_at.desc())

        if district:
            stmt = stmt.where(Property.district.ilike(f"%{district}%"))
        if country:
            stmt = stmt.where(Property.country.ilike(f"%{country}%"))
        if price_min is not None:
            stmt = stmt.where(Property.price_monthly >= price_min)
        if price_max is not None:
            stmt = stmt.where(Property.price_monthly <= price_max)
        if bedrooms is not None:
            stmt = stmt.where(Property.bedrooms == bedrooms)
        if property_type:
            stmt = stmt.where(cast(Property.property_type, String) == property_type)
        if status:
            stmt = stmt.where(cast(Property.status, String) == status)

        # ── 新增筛选条件 ──
        if institute_id is not None:
            stmt = stmt.where(Property.institute_id == institute_id)
        if female_only is True:
            # 旧库没有性别限制字段，不能把未知数据当成满足硬条件。
            stmt = stmt.where(text("FALSE"))
        if amenities:
            for amenity in amenities:
                stmt = stmt.where(Property.amenities.op("@>")([amenity]))
        # P0 大学距离约束 — bounding box 预筛选
        if near_lat is not None and near_lng is not None and near_distance_km is not None:
            import math as _math
            lat_d = near_distance_km / 111.0
            lng_d = near_distance_km / (111.0 * _math.cos(_math.radians(near_lat)))
            stmt = stmt.where(Property.latitude >= near_lat - lat_d,
                              Property.latitude <= near_lat + lat_d,
                              Property.longitude >= near_lng - lng_d,
                              Property.longitude <= near_lng + lng_d)
        if available_from:
            # 入住月份：YYYYMM → 当月及之前可入住的房源
            year = int(available_from[:4])
            month = int(available_from[4:6])
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            stmt = stmt.where(
                Property.available_from.isnot(None),
                Property.available_from < end_date,
            )
        if room_type:
            stmt = stmt.where(self._room_type_filter_clause(room_type))
        if min_lease_months is not None:
            stmt = stmt.where(Property.max_lease_months >= min_lease_months)
        if max_lease_months is not None:
            stmt = stmt.where(Property.min_lease_months <= max_lease_months)
        if bathrooms is not None:
            stmt = stmt.where(Property.bathrooms >= bathrooms)
        if area_min is not None:
            stmt = stmt.where(Property.area_sqm >= area_min)
        if area_max is not None:
            stmt = stmt.where(Property.area_sqm <= area_max)
        # ── 排序 ──
        if sort_by == "price_asc":
            stmt = stmt.order_by(Property.price_monthly.asc())
        elif sort_by == "price_desc":
            stmt = stmt.order_by(Property.price_monthly.desc())
        elif sort_by == "created_at":
            stmt = stmt.order_by(Property.created_at.desc())

        stmt = stmt.where(cast(Property.status, String) == "available")
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows = result.all()
        results = [(row[0], row[1]) for row in rows]

        # 向量搜索 0 结果回退：房源均无 embedding → 关键词 ILIKE 搜索
        if len(results) == 0 and query_vec is not None and query:
            logger.info("SEARCH vector returned 0 results, falling back to keyword ILIKE")
            from sqlalchemy import or_
            fallback_stmt = (
                select(Property, text("NULL AS similarity"))
                .options(*self._legacy_read_options())
                .where(Property.deleted_at.is_(None))
            )
            kw = f"%{query}%"
            fallback_stmt = fallback_stmt.where(or_(
                Property.title.ilike(kw),
                Property.address.ilike(kw),
                Property.district.ilike(kw),
                Property.description.ilike(kw),
            ))
            if district:
                fallback_stmt = fallback_stmt.where(Property.district.ilike(f"%{district}%"))
            if country:
                fallback_stmt = fallback_stmt.where(Property.country.ilike(f"%{country}%"))
            if price_min is not None:
                fallback_stmt = fallback_stmt.where(Property.price_monthly >= price_min)
            if price_max is not None:
                fallback_stmt = fallback_stmt.where(Property.price_monthly <= price_max)
            if bedrooms is not None:
                fallback_stmt = fallback_stmt.where(Property.bedrooms == bedrooms)
            if property_type:
                fallback_stmt = fallback_stmt.where(cast(Property.property_type, String) == property_type)
            if status:
                fallback_stmt = fallback_stmt.where(cast(Property.status, String) == status)

            # ── 新增筛选条件（回退路径）──
            if institute_id is not None:
                fallback_stmt = fallback_stmt.where(Property.institute_id == institute_id)
            if amenities:
                for amenity in amenities:
                    fallback_stmt = fallback_stmt.where(Property.amenities.op("@>")([amenity]))
            if available_from:
                year = int(available_from[:4])
                month = int(available_from[4:6])
                if month == 12:
                    end_date = date(year + 1, 1, 1)
                else:
                    end_date = date(year, month + 1, 1)
                fallback_stmt = fallback_stmt.where(
                    Property.available_from.isnot(None),
                    Property.available_from < end_date,
                )
            if room_type:
                fallback_stmt = fallback_stmt.where(self._room_type_filter_clause(room_type))
            if min_lease_months is not None:
                fallback_stmt = fallback_stmt.where(Property.max_lease_months >= min_lease_months)
            if max_lease_months is not None:
                fallback_stmt = fallback_stmt.where(Property.min_lease_months <= max_lease_months)
            if bathrooms is not None:
                fallback_stmt = fallback_stmt.where(Property.bathrooms >= bathrooms)
            if area_min is not None:
                fallback_stmt = fallback_stmt.where(Property.area_sqm >= area_min)
            if area_max is not None:
                fallback_stmt = fallback_stmt.where(Property.area_sqm <= area_max)
            fallback_stmt = fallback_stmt.where(cast(Property.status, String) == "available")
            fallback_stmt = fallback_stmt.order_by(Property.created_at.desc())
            fallback_stmt = fallback_stmt.limit(limit)
            fallback_result = await self.session.execute(fallback_stmt)
            results = [(row[0], row[1]) for row in fallback_result.all()]

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

        results = [
            (self._apply_legacy_defaults(prop), similarity)
            for prop, similarity in results
        ]

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

        update_data = self._normalize_room_write_payload(
            property_in.model_dump(exclude_unset=True)
        )
        # version 由服务端自增，不从客户端取值
        update_data.pop("version", None)

        # 记录旧值，供回滚使用
        old_values = {}
        for key in update_data:
            old_val = getattr(property_obj, key, None)
            if hasattr(old_val, 'value'):  # 枚举类型取 value
                old_val = old_val.value
            elif hasattr(old_val, 'isoformat'):  # 日期类型转字符串
                old_val = old_val.isoformat()
            elif isinstance(old_val, Decimal):
                old_val = str(old_val)
            old_values[key] = old_val

        for key, value in update_data.items():
            setattr(property_obj, key, value)

        # 自动递增版本号
        property_obj.version = (property_obj.version or 0) + 1
        property_obj.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(property_obj)

        # 异步派发 Google Maps 全量 POI 检索（不阻塞更新流程）
        try:
            from app.tasks.poi_tasks import generate_full_poi_for_property
            generate_full_poi_for_property.delay(property_obj.id)
        except Exception:
            logger.exception("Failed to dispatch POI task for property %s", property_obj.id)

        await self._ensure_embedding(property_obj)
        await _bump_search_cache_version()

        await self._audit(property_obj.landlord_id, "property_update", property_obj.id,
                          {"title": property_obj.title, "changed_fields": list(update_data.keys()),
                           "old_values": old_values,
                           "new_values": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in update_data.items()},
                           "property_title": property_obj.title,
                           "property_address": property_obj.address,
                           "institute_name": getattr(property_obj, "institute_name", None)})

        return property_obj

    async def delete(self, property_id: int) -> bool:
        """软删除：设置 deleted_at"""
        property_obj = await self.get(property_id)
        if not property_obj:
            return False
        self._apply_delete(property_obj)
        await self.session.commit()
        await self._audit(property_obj.landlord_id, "property_delete", property_obj.id,
                          {"title": property_obj.title,
                           "property_title": property_obj.title,
                           "property_address": property_obj.address,
                           "institute_name": getattr(property_obj, "institute_name", None)})
        return True

    @staticmethod
    def _apply_delete(property_obj: Property) -> None:
        """标记软删除（不提交事务）。"""
        property_obj.deleted_at = datetime.now(timezone.utc)
        property_obj.status = PropertyStatus.offline

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
        await self._audit(property_obj.landlord_id, "property_restore", property_obj.id,
                          {"title": property_obj.title,
                           "property_title": property_obj.title,
                           "property_address": property_obj.address,
                           "institute_name": getattr(property_obj, "institute_name", None)})
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
        """批量软删除

        异常处理策略：
        - 单条业务级错误（房源不存在、字段异常等）写入 errors 列表，不抛异常
        - 提交阶段的异常被捕获，回滚后将失败信息追加到 errors，确保前端能拿到明细
        - 审计日志写入失败不影响主体业务结果，仅记录日志
        """
        now = datetime.now(timezone.utc)
        deleted = 0
        errors: list[dict] = []
        property_snapshots: list[dict] = []

        # 阶段 1：内存中逐条标记软删除（不提交）
        for pid in ids:
            try:
                prop = await self.get(pid)
                if prop:
                    property_snapshots.append({
                        "id": prop.id, "title": prop.title,
                        "address": prop.address,
                        "institute_name": getattr(prop, "institute_name", None),
                    })
                    prop.deleted_at = now
                    prop.status = PropertyStatus.offline
                    deleted += 1
                else:
                    errors.append({"id": pid, "error": "房源不存在"})
            except Exception as e:
                # 单条异常不影响其他记录，但加入 errors 列表
                errors.append({"id": pid, "error": str(e)})

        # 阶段 2：判断是否需要回滚
        if errors and deleted == 0:
            # 全部失败：回滚所有内存修改，返回错误明细
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        # 阶段 3：单次事务提交
        commit_error: str | None = None
        try:
            await self.session.commit()
        except Exception as e:
            commit_error = str(e)
            await self.session.rollback()
            # 将整批提交失败标记到 errors，前端可见
            errors.append({"id": None, "error": f"批量提交失败：{commit_error}"})

        # 阶段 4：审计日志（失败不影响返回结果）
        if commit_error is None:
            try:
                await self._audit(landlord_id, "property_batch_delete", 0,
                                  {"ids": ids, "deleted": deleted, "properties": property_snapshots})
            except Exception:
                logger.exception("Audit log write failed for batch_delete")

        return {"success": deleted, "failed": len(errors), "errors": errors}

    async def hard_delete(self, property_id: int) -> bool:
        """物理删除：从数据库彻底移除（回收站专用）"""
        from sqlalchemy.orm import selectinload
        stmt = select(Property).where(Property.id == property_id, Property.deleted_at.isnot(None)).options(selectinload(Property.institute))
        result = await self.session.execute(stmt)
        property_obj = result.scalars().first()
        if not property_obj:
            return False
        institute_name = property_obj.institute.name if property_obj.institute else None
        await self.session.delete(property_obj)
        await self.session.commit()
        await _bump_search_cache_version()
        await self._audit(property_obj.landlord_id, 'property_hard_delete', property_obj.id,
                          {'title': property_obj.title,
                           'property_title': property_obj.title,
                           'property_address': property_obj.address,
                           'institute_name': institute_name})
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
        from app.services.embedding_service import get_embedding_service

        embedding_service = get_embedding_service()
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

    async def batch_restore(self, ids: list[int], landlord_id: int) -> dict:
        """批量恢复

        异常处理策略：
        - 单条业务级错误（房源不存在、未被删除等）写入 errors 列表，不抛异常
        - 提交阶段的异常被捕获，回滚后将失败信息追加到 errors
        - 审计日志写入失败不影响主体业务结果
        """
        restored = 0
        errors: list[dict] = []
        property_snapshots: list[dict] = []

        # 阶段 1：内存中逐条恢复（不提交）
        for pid in ids:
            try:
                from sqlalchemy.orm import selectinload
                stmt = select(Property).where(Property.id == pid, Property.deleted_at.isnot(None)).options(selectinload(Property.institute))
                result = await self.session.execute(stmt)
                prop = result.scalars().first()
                if prop:
                    property_snapshots.append({
                        "id": prop.id, "title": prop.title,
                        "address": prop.address,
                        "institute_name": prop.institute.name if prop.institute else None,
                    })
                    prop.deleted_at = None
                    prop.status = PropertyStatus.available
                    restored += 1
                else:
                    errors.append({"id": pid, "error": "房源不存在或未被删除"})
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})

        # 阶段 2：判断是否需要回滚
        if errors and restored == 0:
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        # 阶段 3：单次事务提交
        commit_error: str | None = None
        try:
            await self.session.commit()
        except Exception as e:
            commit_error = str(e)
            await self.session.rollback()
            errors.append({"id": None, "error": f"批量提交失败：{commit_error}"})

        # 阶段 4：审计日志
        if commit_error is None:
            try:
                await self._audit(landlord_id, 'property_batch_restore', 0,
                                  {'ids': ids, 'restored': restored, 'properties': property_snapshots})
            except Exception:
                logger.exception("Audit log write failed for batch_restore")

        return {'success': restored, 'failed': len(errors), 'errors': errors}

    async def batch_hard_delete(self, ids: list[int], landlord_id: int) -> dict:
        """批量物理删除

        异常处理策略：
        - 单条业务级错误写入 errors，不抛异常
        - 提交阶段异常被捕获，回滚后将失败信息追加到 errors
        - 审计日志写入失败不影响主体业务结果
        """
        from sqlalchemy.orm import selectinload
        deleted = 0
        errors: list[dict] = []
        property_snapshots: list[dict] = []

        # 阶段 1：内存中逐条标记删除（不提交）
        for pid in ids:
            try:
                stmt = select(Property).where(Property.id == pid, Property.deleted_at.isnot(None)).options(selectinload(Property.institute))
                result = await self.session.execute(stmt)
                prop = result.scalars().first()
                if prop:
                    property_snapshots.append({
                        "id": prop.id, "title": prop.title,
                        "address": prop.address,
                        "institute_name": prop.institute.name if prop.institute else None,
                    })
                    await self.session.delete(prop)
                    deleted += 1
                else:
                    errors.append({"id": pid, "error": "房源不存在或未被删除"})
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})

        # 阶段 2：全部失败则回滚
        if errors and deleted == 0:
            await self.session.rollback()
            return {"success": 0, "failed": len(ids), "errors": errors}

        # 阶段 3：单次事务提交
        commit_error: str | None = None
        try:
            await self.session.commit()
        except Exception as e:
            commit_error = str(e)
            await self.session.rollback()
            errors.append({"id": None, "error": f"批量提交失败：{commit_error}"})

        # 阶段 4：缓存失效 + 审计日志
        if commit_error is None:
            await _bump_search_cache_version()
            try:
                await self._audit(landlord_id, 'property_batch_hard_delete', 0,
                                  {'ids': ids, 'deleted': deleted, 'properties': property_snapshots})
            except Exception:
                logger.exception("Audit log write failed for batch_hard_delete")

        return {'success': deleted, 'failed': len(errors), 'errors': errors}

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

    async def get_recent_audit(
        self,
        landlord_id: int,
        *,
        limit: int = 20,
    ) -> list[dict]:
        """获取当前房东所有房源最近的操作审计日志"""
        from app.models.audit_log import AuditLog
        from sqlalchemy import or_

        # 先获取该房东的所有房源 ID
        prop_ids_stmt = select(Property.id).where(
            Property.landlord_id == landlord_id,
        )
        prop_ids_result = await self.session.scalars(prop_ids_stmt)
        prop_ids = set(prop_ids_result.all())

        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type == "property",
                or_(
                    AuditLog.resource_id.in_(prop_ids),
                    AuditLog.user_id == landlord_id,
                ),
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

    async def _get_property_any(self, property_id: int) -> Property | None:
        """查询房源，不过滤 deleted_at（用于撤销已删除房源的操作）"""
        from sqlalchemy.orm import selectinload
        stmt = select(Property).where(Property.id == property_id).options(
            selectinload(Property.institute),
            selectinload(Property.images),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    REVERTABLE_ACTIONS = {"property_create", "property_update", "property_delete", "property_restore"}

    async def revert_audit(
        self,
        property_id: int,
        audit_log_id: int,
        current_user_id: int,
    ) -> dict:
        """撤销某条审计日志对应的房源操作"""
        from datetime import date as date_type
        from app.services.audit_service import AuditService

        # 1. 获取并校验审计日志
        audit_log = await AuditService(self.session).get_log(audit_log_id)
        if not audit_log:
            raise ValueError("审计记录不存在")
        if audit_log.resource_type != "property" or audit_log.resource_id != property_id:
            raise ValueError("审计记录与房源不匹配")

        action = audit_log.action

        # 2. 检查是否可撤销
        if action not in self.REVERTABLE_ACTIONS:
            if action == "property_hard_delete":
                raise ValueError("硬删除操作无法撤销，房源已物理删除")
            if action.startswith("property_batch_"):
                raise ValueError("批量操作不支持单次撤销，请手动处理")
            raise ValueError(f"不支持撤销此操作类型：{action}")

        # 3. 获取房源（不过滤删除状态）
        property_obj = await self._get_property_any(property_id)
        if not property_obj:
            raise ValueError("房源不存在")

        # 4. 校验所有权
        if current_user_id != property_obj.landlord_id:
            # admin 可以操作任意房源
            from app.services.user_service import UserService
            user = await UserService(self.session).get(current_user_id)
            if not user or user.role.value != "admin":
                raise ValueError("无权操作此房源")

        message = ""

        # 5. 按操作类型执行撤销
        if action == "property_create":
            if property_obj.deleted_at is not None:
                raise ValueError("该房源已被删除，无法撤销创建操作")
            self._apply_delete(property_obj)
            message = "已撤销房源创建，房源已被软删除"

        elif action == "property_update":
            if property_obj.deleted_at is not None:
                raise ValueError("该房源已被删除，无法撤销修改操作")
            old_values = (audit_log.details or {}).get("old_values")
            if not old_values or not isinstance(old_values, dict):
                raise ValueError("该审计记录中没有旧值数据，无法撤销")

            for key, value in old_values.items():
                try:
                    converted = self._convert_old_value(key, value)
                    setattr(property_obj, key, converted)
                except Exception:
                    logger.warning("Failed to revert field %s to value %s, skipping", key, value)

            property_obj.version = (property_obj.version or 0) + 1
            property_obj.updated_at = datetime.now(timezone.utc)
            message = "已撤销房源修改，已恢复至修改前的值"

        elif action == "property_delete":
            if property_obj.deleted_at is None:
                raise ValueError("该房源未被删除，无法撤销删除操作")
            property_obj.deleted_at = None
            property_obj.status = PropertyStatus.available
            message = "已撤销房源删除，房源已恢复"

        elif action == "property_restore":
            if property_obj.deleted_at is not None:
                raise ValueError("该房源已被删除，无法撤销恢复操作")
            self._apply_delete(property_obj)
            message = "已撤销房源恢复，房源已被重新软删除"

        await self.session.commit()

        # 6. 记录撤销审计
        await self._audit(
            current_user_id,
            "property_revert",
            property_id,
            {
                "reverted_action": action,
                "reverted_audit_log_id": audit_log_id,
                "message": message,
                "property_title": property_obj.title,
                "property_address": property_obj.address,
                "institute_name": getattr(property_obj, "institute_name", None),
            },
        )

        return {
            "message": message,
            "property_id": property_id,
            "reverted_action": action,
        }

    @staticmethod
    def _convert_old_value(key: str, value):
        """将审计日志中序列化的旧值还原为 Python 类型"""
        if value is None:
            return None
        # 枚举
        if key == "property_type":
            return PropertyType(value)
        if key == "status":
            return PropertyStatus(value)
        if key == "deposit_type":
            return DepositType(value) if value else None
        # Decimal
        if key in ("price_monthly", "area_sqm", "latitude", "longitude"):
            return Decimal(str(value)) if value is not None else None
        # Date
        if key == "available_from":
            from datetime import date as date_type
            if isinstance(value, str):
                return date_type.fromisoformat(value)
            return value
        # Int
        if key in ("bedrooms", "bathrooms", "deposit_amount", "floor", "min_stay_months", "institute_id"):
            return int(value) if value is not None else None
        # Float
        if key == "service_fee_rate":
            return float(value) if value is not None else None
        # List
        if key == "amenities":
            return list(value) if isinstance(value, list) else value
        return value

    async def _audit(self, user_id: int, action: str, resource_id: int, details: dict) -> bool:
        """写入审计日志，返回是否成功。失败不阻塞主流程但会输出可见警告。"""
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
                f"\n[!] ⚠️ 审计日志写入失败！操作={action}, 房源ID={resource_id}, 用户ID={user_id}",
                file=sys.stderr,
            )
            return False

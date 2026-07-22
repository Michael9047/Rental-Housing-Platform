# 地图 POI 预生成 Celery 任务
# 房源创建/更新时异步触发，搜索 3km 内 6 大类 POI 并存入 PropertyPOI.map_poi_data
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.poi import PropertyPOI
from app.models.property import Property
from app.services.poi_service import POIService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="generate_map_pois_for_property",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_map_pois_for_property(property_id: int) -> None:
    """异步生成房源地图 POI 数据，存入 PropertyPOI.map_poi_data"""

    import asyncio

    async def _run() -> None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        # dispose 必须在 finally 里：下面两条提前 return 和任何异常都会跳过它，
        # 每次泄漏一个未关闭的连接池，最终打满 Postgres 的 max_connections。
        try:
            async with async_session() as session:
                prop = await session.get(Property, property_id)
                if not prop:
                    logger.warning("Map POI task: property %s not found", property_id)
                    return

                poi_service = POIService(session)
                data = await poi_service.generate_map_pois(prop)
                if not data:
                    logger.warning("Map POI task: empty results for property %s", property_id)
                    return

                # Upsert 到 PropertyPOI
                result = await session.execute(
                    select(PropertyPOI).where(PropertyPOI.property_id == property_id)
                )
                poi = result.scalar_one_or_none()
                if poi:
                    poi.map_poi_data = data
                    poi.generated_at = datetime.now(timezone.utc)
                else:
                    poi = PropertyPOI(
                        property_id=property_id,
                        content="",
                        map_poi_data=data,
                        generated_at=datetime.now(timezone.utc),
                        reviewed=False,
                    )
                    session.add(poi)

                await session.commit()
                logger.info("Map POI generated for property %s: %d categories",
                            property_id, len(data.get("categories", {})))
        finally:
            await engine.dispose()

    asyncio.run(_run())


@celery_app.task(
    name="backfill_all_map_pois",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=1,
)
def backfill_all_map_pois() -> int:
    """存量房源批量补生成地图 POI（查找 map_poi_data 为空的房源）"""

    import asyncio

    async def _run() -> int:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with async_session() as session:
                # 单次 outer join 找出缺失缓存，避免逐房源 N+1 查询。
                result = await session.execute(
                    select(Property.id)
                    .outerjoin(PropertyPOI, PropertyPOI.property_id == Property.id)
                    .where(
                        Property.latitude.isnot(None),
                        Property.longitude.isnot(None),
                        Property.deleted_at.is_(None),
                        or_(
                            PropertyPOI.id.is_(None),
                            PropertyPOI.map_poi_data.is_(None),
                        ),
                    )
                )
                missing = [row[0] for row in result.all()]
        finally:
            await engine.dispose()

        for pid in missing:
            generate_map_pois_for_property.delay(pid)

        logger.info("Backfill enqueued: %d properties for map POI generation", len(missing))
        return len(missing)

    return asyncio.run(_run())


@celery_app.task(name="refresh_stale_map_pois")
def refresh_stale_map_pois(limit: int | None = None) -> int:
    """批量投递缺失或过期的地图 POI 缓存刷新任务。

    刻意不加 autoretry：这是扇出型任务，若在 .delay() 循环中途失败，
    重试会重新查库（子任务尚未更新 generated_at，同一批仍全部命中）
    并把已投递的部分再投一遍。beat 每 poi_refresh_interval_seconds
    就会再跑一次，跳过一个周期比重复扇出便宜得多。
    """

    import asyncio

    async def _run() -> list[int]:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.poi_map_cache_ttl_hours)
        batch_size = min(max(1, limit or settings.poi_refresh_batch_size), 5000)

        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Property.id)
                    .outerjoin(PropertyPOI, PropertyPOI.property_id == Property.id)
                    .where(
                        Property.latitude.isnot(None),
                        Property.longitude.isnot(None),
                        # 软删除的房源行还在表里；不排除的话每个刷新周期都会
                        # 给它们重新生成一次 POI，白烧地图 API 配额。
                        Property.deleted_at.is_(None),
                        or_(
                            PropertyPOI.id.is_(None),
                            PropertyPOI.map_poi_data.is_(None),
                            PropertyPOI.generated_at < cutoff,
                        ),
                    )
                    .order_by(PropertyPOI.generated_at.asc().nullsfirst(), Property.id.asc())
                    .limit(batch_size)
                )
                property_ids = [row[0] for row in result.all()]
        finally:
            await engine.dispose()
        return property_ids

    stale_ids = asyncio.run(_run())
    for property_id in stale_ids:
        generate_map_pois_for_property.delay(property_id)
    logger.info("Stale map POI refresh enqueued: %d properties", len(stale_ids))
    return len(stale_ids)

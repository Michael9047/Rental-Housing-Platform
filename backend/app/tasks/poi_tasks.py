# 地图 POI 预生成 Celery 任务
# 房源创建/更新时异步触发，搜索 3km 内 6 大类 POI 并存入 PropertyPOI.map_poi_data
import logging
from datetime import datetime, timezone

from sqlalchemy import select
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

        async with async_session() as session:
            # 查找有坐标但 map_poi_data 缺失的房源
            from sqlalchemy import and_, or_
            result = await session.execute(
                select(Property.id)
                .where(
                    Property.latitude.isnot(None),
                    Property.longitude.isnot(None),
                )
            )
            all_ids = [row[0] for row in result.all()]

            # 检查哪些还没有 map_poi_data
            missing: list[int] = []
            for pid in all_ids:
                poi_result = await session.execute(
                    select(PropertyPOI.map_poi_data)
                    .where(PropertyPOI.property_id == pid)
                )
                row = poi_result.first()
                if not row or not row[0]:
                    missing.append(pid)

        await engine.dispose()

        for pid in missing:
            generate_map_pois_for_property.delay(pid)

        logger.info("Backfill enqueued: %d properties for map POI generation", len(missing))
        return len(missing)

    return asyncio.run(_run())

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.property import Property
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="generate_property_embedding",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_property_embedding(property_id: int) -> None:
    import asyncio

    async def _run() -> None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)

        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            property_obj = await session.get(Property, property_id)
            if not property_obj:
                logger.warning("Property %s not found for embedding generation", property_id)
                return

            embedding_service = EmbeddingService()
            text_data = {
                "title": property_obj.title,
                "description": property_obj.description,
                "address": property_obj.address,
                "district": property_obj.district,
                "property_type": property_obj.property_type.value,
            }
            property_obj.embedding = await embedding_service.generate_property_embedding(text_data)
            await session.commit()
            logger.info("Embedding generated for property %s", property_id)

        await engine.dispose()

    asyncio.run(_run())


@celery_app.task(
    name="reindex_all_properties",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def reindex_all_properties() -> int:
    import asyncio

    async def _run() -> int:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(
                select(Property.id).where(Property.embedding.is_(None))
            )
            property_ids = [row[0] for row in result.all()]

        await engine.dispose()

        for pid in property_ids:
            generate_property_embedding.delay(pid)

        logger.info("Enqueued %s properties for reindex", len(property_ids))
        return len(property_ids)

    return asyncio.run(_run())
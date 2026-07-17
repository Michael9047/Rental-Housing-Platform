import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.property import Property

logger = logging.getLogger(__name__)


@celery_app.task(
    name="batch_embedding_new_properties",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def batch_embedding_new_properties() -> int:
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

        from app.tasks.embedding_tasks import generate_property_embedding

        for pid in property_ids:
            generate_property_embedding.delay(pid)

        logger.info("Batch embedding: enqueued %s properties", len(property_ids))
        return len(property_ids)

    return asyncio.run(_run())

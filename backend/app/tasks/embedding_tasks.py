import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.embedding_job import EmbeddingJob, EmbeddingJobStatus
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
            # Create pending EmbeddingJob
            job = EmbeddingJob(
                property_id=property_id,
                status=EmbeddingJobStatus.pending,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)

            try:
                # Mark as processing
                job.status = EmbeddingJobStatus.processing
                job.started_at = datetime.now(timezone.utc)
                await session.commit()

                property_obj = await session.get(Property, property_id)
                if not property_obj:
                    job.status = EmbeddingJobStatus.failed
                    job.error_message = f"Property {property_id} not found"
                    job.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.warning("Property %s not found for embedding generation", property_id)
                    return

                # Celery 任务每次用 asyncio.run() 起独立事件循环，
                # 故此处必须每次新建 EmbeddingService（不能用进程级单例，
                # 否则内部 AsyncOpenAI/redis client 会绑定到已关闭的 loop）。
                embedding_service = EmbeddingService()
                text_data = {
                    "title": property_obj.title,
                    "description": property_obj.description,
                    "address": property_obj.address,
                    "district": property_obj.district,
                    "property_type": property_obj.property_type.value,
                }
                # 返回 list[float]，直接写入 pgvector Vector 列
                property_obj.embedding = await embedding_service.generate_property_embedding(text_data)

                job.status = EmbeddingJobStatus.completed
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info("Embedding generated for property %s (job %s)", property_id, job.id)

            except Exception as exc:
                job.status = EmbeddingJobStatus.failed
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.exception("Embedding generation failed for property %s", property_id)
                raise

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

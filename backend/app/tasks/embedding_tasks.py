import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.embedding_job import EmbeddingJob, EmbeddingJobStatus
from app.models.unit_type import UnitType
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def build_unit_type_embedding_payload(unit_type: UnitType) -> dict[str, str]:
    """构建去标识化户型特征；外部向量服务不接收名称、描述或地址。"""
    institute = getattr(unit_type, "institute", None)
    property_type = getattr(unit_type, "property_type", None)
    property_type_text = (
        str(property_type.value)
        if hasattr(property_type, "value")
        else str(property_type or "")
    )
    bedrooms = int(getattr(unit_type, "bedrooms", 0) or 0)
    bathrooms = int(getattr(unit_type, "bathrooms", 0) or 0)
    country = str(getattr(institute, "country", None) or "")
    return {
        "title": "Rental unit",
        "description": f"{bedrooms} bedrooms {bathrooms} bathrooms".strip(),
        "address": "",
        # 保留既有 payload 键，但只提供国家级位置，不发送区域或精确地址。
        "district": country,
        "property_type": property_type_text,
    }


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

                unit_type = await session.scalar(
                    select(UnitType)
                    .options(selectinload(UnitType.institute))
                    .where(UnitType.id == property_id, UnitType.deleted_at.is_(None))
                )
                if not unit_type:
                    job.status = EmbeddingJobStatus.failed
                    job.error_message = f"UnitType {property_id} not found"
                    job.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.warning("UnitType %s not found for embedding generation", property_id)
                    return

                embedding_service = EmbeddingService()
                text_data = build_unit_type_embedding_payload(unit_type)
                unit_type.embedding = await embedding_service.generate_property_embedding(text_data)

                job.status = EmbeddingJobStatus.completed
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info("Embedding generated for UnitType %s (job %s)", property_id, job.id)

            except Exception as exc:
                job.status = EmbeddingJobStatus.failed
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.exception("Embedding generation failed for UnitType %s", property_id)
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
                select(UnitType.id).where(
                    UnitType.embedding.is_(None),
                    UnitType.deleted_at.is_(None),
                )
            )
            property_ids = [row[0] for row in result.all()]

        await engine.dispose()

        for pid in property_ids:
            generate_property_embedding.delay(pid)

        logger.info("Enqueued %s properties for reindex", len(property_ids))
        return len(property_ids)

    return asyncio.run(_run())

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.embedding_job import EmbeddingJob, EmbeddingJobStatus


class EmbeddingJobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_jobs(self, *, skip: int = 0, limit: int = 50) -> list[EmbeddingJob]:
        stmt = (
            select(EmbeddingJob)
            .order_by(EmbeddingJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def get_stats(self) -> dict:
        total = await self.session.scalar(select(func.count(EmbeddingJob.id)))
        completed = await self.session.scalar(
            select(func.count(EmbeddingJob.id)).where(
                EmbeddingJob.status == EmbeddingJobStatus.completed
            )
        )
        failed = await self.session.scalar(
            select(func.count(EmbeddingJob.id)).where(
                EmbeddingJob.status == EmbeddingJobStatus.failed
            )
        )
        pending = await self.session.scalar(
            select(func.count(EmbeddingJob.id)).where(
                EmbeddingJob.status == EmbeddingJobStatus.pending
            )
        )
        return {
            "total": total or 0,
            "completed": completed or 0,
            "failed": failed or 0,
            "pending": pending or 0,
        }

    async def trigger_reindex(self, property_id: int | None = None) -> dict:
        from app.tasks.embedding_tasks import generate_property_embedding, reindex_all_properties

        redis_available = False
        try:
            from redis.asyncio import Redis as AsyncRedis

            redis = AsyncRedis.from_url(
                get_settings().redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
                decode_responses=False,
            )
            await redis.ping()
            await redis.aclose()
            redis_available = True
        except Exception as exc:
            return {
                "detail": "Embedding queue is unavailable",
                "queued": False,
                "reason": str(exc)[:300],
                "property_id": property_id,
            }

        if property_id:
            generate_property_embedding.delay(property_id)
            return {"detail": f"Reindex triggered for property {property_id}", "queued": redis_available}
        else:
            count = reindex_all_properties.delay()
            return {"detail": "Reindex triggered for all properties", "queued": redis_available, "count": str(count)}

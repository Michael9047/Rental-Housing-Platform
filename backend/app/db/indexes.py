"""Database index optimization for pgvector and high-frequency queries.

Provides utilities to create performance indexes on PostgreSQL + pgvector,
including IVFFlat tuning and composite indexes for common access patterns."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def create_pgvector_indexes(session: AsyncSession) -> None:
    """Create or re-create IVFFlat indexes on property embeddings with adaptive lists parameter.

    IVFFlat `lists` parameter should be roughly sqrt(row_count) for optimal recall/performance.
    If fewer than 1000 rows exist a simple exact-neighbor scan is used instead.
    """
    result = await session.execute(
        text("SELECT COUNT(*) FROM properties WHERE embedding IS NOT NULL")
    )
    row_count: int = result.scalar() or 0

    if row_count < 1000:
        logger.info(
            "Only %d properties with embeddings — exact scan preferred, skipping IVFFlat index.",
            row_count,
        )
        return

    # Check if an IVFFlat index already exists to avoid recreating it
    existing = await session.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_properties_embedding_ivfflat'")
    )
    if existing.scalar():
        logger.info("IVFFlat index already exists on properties.embedding.")
        return

    lists = max(1, int(row_count**0.5))
    logger.info(
        "Creating IVFFlat index on properties.embedding with lists=%d (sqrt of %d rows).",
        lists,
        row_count,
    )
    await session.execute(text(f"CREATE INDEX ix_properties_embedding_ivfflat ON properties USING ivfflat (embedding vector_l2_ops) WITH (lists = {lists})"))


async def create_booking_composite_indexes(session: AsyncSession) -> None:
    """Create composite indexes for common booking query patterns."""
    indexes: list[str] = []

    # Check for existing indexes
    existing = await session.execute(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'bookings'")
    )
    existing_names = {row[0] for row in existing.all()}

    if "ix_bookings_tenant_status" not in existing_names:
        indexes.append(
            "CREATE INDEX IF NOT EXISTS ix_bookings_tenant_status ON bookings (tenant_id, status)"
        )
    if "ix_bookings_landlord_status" not in existing_names:
        indexes.append(
            "CREATE INDEX IF NOT EXISTS ix_bookings_landlord_status ON bookings (landlord_id, status)"
        )
    if "ix_bookings_property_status" not in existing_names:
        indexes.append(
            "CREATE INDEX IF NOT EXISTS ix_bookings_property_status ON bookings (property_id, status)"
        )

    for sql in indexes:
        logger.info("Creating index: %s", sql)
        await session.execute(text(sql))

    if indexes:
        logger.info("Created %d booking composite index(es).", len(indexes))
    else:
        logger.info("All booking composite indexes already exist.")


async def create_all_indexes(session: AsyncSession) -> None:
    """Run all index optimizations."""
    await create_pgvector_indexes(session)
    await create_booking_composite_indexes(session)
    await session.commit()


async def check_query_performance(session: AsyncSession, query_sql: str, query_name: str = "query") -> None:
    """Run EXPLAIN ANALYZE on a query and log the execution plan."""
    logger.info("=== EXPLAIN ANALYZE: %s ===", query_name)
    result = await session.execute(text(f"EXPLAIN ANALYZE {query_sql}"))
    for row in result.all():
        logger.info("  %s", row[0])
    logger.info("=== END EXPLAIN ANALYZE: %s ===", query_name)


async def run_performance_checks(session: AsyncSession) -> None:
    """Run performance checks on common queries."""
    queries = [
        ("SELECT p.*, p.created_at FROM properties p WHERE p.district = $1 AND p.status = $2 ORDER BY p.created_at DESC LIMIT 20",
         "Property Search (district + status)", ["Changning", "available"]),
        ("SELECT b.* FROM bookings b WHERE b.tenant_id = $1 AND b.status = $2 ORDER BY b.created_at DESC LIMIT 50",
         "Tenant Bookings (user + status)", ["1", "pending"]),
        ("SELECT b.* FROM bookings b WHERE b.landlord_id = $1 AND b.status = $2 ORDER BY b.created_at DESC LIMIT 50",
         "Landlord Bookings (user + status)", ["1", "pending"]),
    ]

    for sql, name, params in queries:
        # Simple EXPLAIN ANALYZE doesn't support params; log approximate
        try:
            safe_sql = sql.replace("$1", f"''{params[0]}''").replace("$2", f"''{params[1]}''")
            await check_query_performance(session, safe_sql, name)
        except Exception:
            logger.exception("Failed to analyze query: %s", name)

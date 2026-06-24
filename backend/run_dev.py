"""
Development launcher — uses SQLite instead of PostgreSQL so you can run the API
without Docker. Start with:

    .venv/Scripts/python run_dev.py

Then open http://localhost:8000/docs for the Swagger UI.
"""
import os
import sys


def _patch_for_dev():
    """Override settings so the app boots with SQLite and no Redis dependency."""
    # Use SQLite (same as the test suite)
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./dev.db"
    os.environ["ALEMBIC_DATABASE_URL"] = "sqlite+aiosqlite:///./dev.db"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DEBUG"] = "true"
    os.environ["CORS_ORIGINS"] = '["*"]'
    # Disable external services to keep startup snappy
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("AMAP_WEB_KEY", "")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    # Make Celery run tasks inline (no broker needed)
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "true"


def _create_tables():
    """Create all tables via SQLAlchemy metadata (equivalent to alembic upgrade)."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.db.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///./dev.db", echo=False)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables created (SQLite)")

    asyncio.run(_init())


if __name__ == "__main__":
    _patch_for_dev()
    _create_tables()

    import uvicorn

    print(">>> Starting dev server at http://localhost:8000")
    print(">>> Swagger docs: http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

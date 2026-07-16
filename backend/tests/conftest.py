import os
from collections.abc import AsyncGenerator

# Ensure tests never call external APIs or require Redis.
# NOTE: these must cover every LLM/embedding provider key the app knows about.
# Environment variables take priority over a developer's local backend/.env
# (which may hold real keys for manual testing), so without this, tests would
# silently start making live network calls the moment a real .env exists.
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("ZHIPU_API_KEY", "")
os.environ.setdefault("AMAP_WEB_KEY", "")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("CELERY_TASK_EAGER_PROPAGATES", "true")
# 测试期关闭搜索缓存：每个用例用全新的内存数据库，但缓存键只按筛选条件算、
# 不区分数据库，共享的 Redis 会把上一个用例的搜索结果串给下一个用例。
# 只关缓存、不动 REDIS_URL —— Celery 的 broker 也读同一个 URL，把它改成非法
# scheme 会让 kombu 在派发任务时抛 "No such transport"。
os.environ.setdefault("CACHE_ENABLED", "false")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db_session
from app.db.session import Base
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def landlord_payload() -> dict[str, str]:
    return {
        "username": "landlord_demo",
        "email": "landlord@example.com",
        "role": "landlord",
    }


@pytest.fixture
def landlord_register_payload() -> dict[str, str]:
    return {
        "username": "auth_landlord",
        "email": "auth_landlord@example.com",
        "password": "secure-password",
        "role": "landlord",
    }


@pytest.fixture
def property_payload() -> dict[str, str | int]:
    return {
        "title": "Sunny two-bedroom apartment",
        "description": "Near metro with good natural light.",
        "address": "88 University Road",
        "district": "SIP",
        "price_monthly": "5200.00",
        "area_sqm": "72.50",
        "bedrooms": 2,
        "bathrooms": 1,
        "property_type": "apartment",
        "status": "available",
    }


def pytest_addoption(parser):
    parser.addoption(
        "--run-pgvector",
        action="store_true",
        default=False,
        help="Run tests that require a real PostgreSQL with pgvector",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "pgvector: tests requiring real PostgreSQL with pgvector extension",
    )


def pytest_collection_modifyitems(config, items):
    import pytest
    if config.getoption("--run-pgvector"):
        return
    skip_pgvector = pytest.mark.skip(reason="Need --run-pgvector flag to run pgvector tests")
    for item in items:
        if "pgvector" in item.keywords:
            item.add_marker(skip_pgvector)

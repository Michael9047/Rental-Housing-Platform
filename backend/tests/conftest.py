from collections.abc import AsyncGenerator

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

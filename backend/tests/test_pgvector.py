import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db_session
from app.main import app

pytestmark = pytest.mark.pgvector


@pytest_asyncio.fixture
async def pg_session():
    """Connect to real PostgreSQL for pgvector tests."""
    from app.core.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_client(pg_session: AsyncSession):
    async def override_get_db_session():
        yield pg_session
    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


class TestPgvectorSearch:
    """Tests requiring real PostgreSQL with pgvector extension."""

    @pytest.mark.asyncio
    async def test_search_by_natural_language(self, pg_client: AsyncClient):
        """Search should return results for Chinese natural language query."""
        response = await pg_client.get("/api/v1/properties/search?q=地铁附近两室")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_search_with_structured_filters(self, pg_client: AsyncClient):
        """Search with both semantic and structured filters."""
        response = await pg_client.get(
            "/api/v1/properties/search",
            params={"q": "工业园区", "district": "工业园区", "price_max": "8000"}
        )
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["district"] == "工业园区"
            assert item["price_monthly"] <= 8000

    @pytest.mark.asyncio
    async def test_property_has_deposit_fields(self, pg_client: AsyncClient):
        """Properties should include deposit fields."""
        response = await pg_client.get("/api/v1/properties?limit=3")
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            p = data[0]
            assert "deposit_amount" in p
            assert "service_fee_rate" in p


class TestPOI:
    """Tests for POI (Points of Interest) feature."""

    @pytest.mark.asyncio
    async def test_generate_poi(self, pg_client: AsyncClient):
        """Generate POI for a property."""
        resp = await pg_client.get("/api/v1/properties?limit=1")
        if resp.status_code != 200 or len(resp.json()) == 0:
            pytest.skip("No properties in database")
        prop_id = resp.json()[0]["id"]

        response = await pg_client.post(f"/api/v1/pois/{prop_id}/generate")
        if response.status_code == 201:
            data = response.json()
            assert "content" in data
            assert "poi_data" in data
            assert len(data["content"]) > 0
        elif response.status_code == 200:
            pass  # Already exists
        else:
            assert response.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_get_poi_returns_data(self, pg_client: AsyncClient):
        """GET POI endpoint returns structured data."""
        resp = await pg_client.get("/api/v1/properties?limit=1")
        if resp.status_code != 200 or len(resp.json()) == 0:
            pytest.skip("No properties")
        prop_id = resp.json()[0]["id"]

        await pg_client.post(f"/api/v1/pois/{prop_id}/generate")

        response = await pg_client.get(f"/api/v1/pois/{prop_id}")
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert isinstance(data["poi_data"], dict)


class TestContracts:
    """Tests for contract generation."""

    @pytest.mark.asyncio
    async def test_contract_endpoints_exist(self, pg_client: AsyncClient):
        """Contract endpoints should be accessible (even if 404 for nonexistent)."""
        resp = await pg_client.get("/api/v1/contracts/99999")
        assert resp.status_code in (401, 404)


class TestPayments:
    """Tests for payment endpoints."""

    @pytest.mark.asyncio
    async def test_payment_endpoints_exist(self, pg_client: AsyncClient):
        """Payment endpoints should be accessible."""
        resp = await pg_client.get("/api/v1/payments/99999")
        assert resp.status_code in (401, 404)


class TestRefreshToken:
    """Tests for JWT refresh token."""

    @pytest.mark.asyncio
    async def test_refresh_endpoint_exists(self, pg_client: AsyncClient):
        """POST /auth/refresh should be a valid endpoint."""
        resp = await pg_client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 401  # Needs valid refresh token

    @pytest.mark.asyncio
    async def test_login_returns_token(self, pg_client: AsyncClient):
        """Login should return access_token."""
        await pg_client.post("/api/v1/auth/register", json={
            "username": "pgtest_user", "password": "test123456",
            "email": "pgtest@test.com"
        })
        resp = await pg_client.post("/api/v1/auth/login", json={
            "username_or_email": "pgtest_user", "password": "test123456"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert resp.json()["token_type"] == "bearer"


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    @pytest.mark.asyncio
    async def test_health_is_unlimited(self, pg_client: AsyncClient):
        """Health endpoint should not be rate limited."""
        for _ in range(5):
            resp = await pg_client.get("/api/v1/health")
            assert resp.status_code == 200

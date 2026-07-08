"""Unit tests for search-cache versioning and sync-first embedding fallback."""
import pytest

from app.services.property_service import PropertyService, _cache_key


def test_cache_key_is_version_scoped() -> None:
    """Cache keys embed the namespace version so a version bump invalidates all."""
    params = {"district": "SIP", "limit": 20}
    k_v0 = _cache_key("filter", "0", **params)
    k_v1 = _cache_key("filter", "1", **params)

    assert k_v0 == "search:filter:v0:" + '{"district": "SIP", "limit": 20}'
    assert k_v0 != k_v1  # bumping the version yields a fresh, unreachable namespace


@pytest.mark.asyncio
async def test_ensure_embedding_falls_back_to_async_without_key(monkeypatch) -> None:
    """With no OpenAI key (the test default), embedding generation defers to the
    async Celery task and never blocks the create/update path."""
    dispatched: list[int] = []
    monkeypatch.setattr(
        PropertyService, "_dispatch_embedding_task", staticmethod(dispatched.append)
    )

    class _StubProp:
        id = 42
        title = "t"
        description = None
        address = "a"
        district = "SIP"
        property_type = "apartment"
        embedding = None

    svc = PropertyService(session=None)  # session unused on the fallback path
    await svc._ensure_embedding(_StubProp())  # type: ignore[arg-type]

    assert dispatched == [42]

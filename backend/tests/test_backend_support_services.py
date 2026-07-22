"""地图、POI、通勤缓存与统一评分 Service 的单元测试。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.commute_service import (
    BatchCommuteResult,
    CommuteDestination,
    CommuteResult,
    calculate_commute_batch_resilient,
)
from app.services.compare_scoring import PropertyMetrics, compute_scores
from app.services.map_service import MapService
from app.services.poi_service import POIService
from app.services.scoring_service import ScoringService


@pytest.mark.asyncio
async def test_commute_cache_only_calculates_misses(monkeypatch) -> None:
    cached_payload = {
        "dist_km": 1.2,
        "walk_min": 15,
        "bike_min": 6,
        "drive_min": 4,
        "transit_min": 8,
        "source": "amap_api",
        "transit_verified": True,
    }
    calculated_ids: list[int | str] = []
    stored_ids: list[int | str] = []

    async def fake_get_many(self, *_args, **_kwargs):
        return {1: cached_payload}

    async def fake_set_many(self, _olat, _olng, destinations, results, **_kwargs):
        stored_ids.extend(result.dest_id for result in results)

    async def fake_close(self):
        return None

    async def fake_uncached(_olat, _olng, destinations, country=None, city=None):
        calculated_ids.extend(destination.dest_id for destination in destinations)
        return BatchCommuteResult(results=[
            CommuteResult(
                dest_id=destination.dest_id,
                dist_km=2.0,
                walk_min=24,
                bike_min=9,
                drive_min=6,
                transit_min=12,
                source="ors_api",
            )
            for destination in destinations
        ], source="ors_api")

    monkeypatch.setattr(
        "app.services.commute_cache_service.CommuteCacheService.get_many",
        fake_get_many,
    )
    monkeypatch.setattr(
        "app.services.commute_cache_service.CommuteCacheService.set_many",
        fake_set_many,
    )
    monkeypatch.setattr(
        "app.services.commute_cache_service.CommuteCacheService.close",
        fake_close,
    )
    monkeypatch.setattr(
        "app.services.commute_service._calculate_commute_batch_resilient_uncached",
        fake_uncached,
    )

    result = await calculate_commute_batch_resilient(
        31.2,
        121.4,
        [
            CommuteDestination(dest_id=1, lat=31.21, lng=121.41),
            CommuteDestination(dest_id=2, lat=31.22, lng=121.42),
        ],
        country="CN",
    )

    assert [item.dest_id for item in result.results] == [1, 2]
    assert result.results[0].transit_verified is True
    assert calculated_ids == [2]
    assert stored_ids == [2]
    assert result.source == "mixed_api"


def test_map_poi_freshness_uses_configurable_ttl() -> None:
    now = datetime.now(timezone.utc)
    fresh = SimpleNamespace(map_poi_data={"categories": {}}, generated_at=now - timedelta(hours=2))
    stale = SimpleNamespace(map_poi_data={"categories": {}}, generated_at=now - timedelta(hours=25))

    assert POIService.is_map_poi_fresh(fresh, now=now, ttl_hours=24)
    assert not POIService.is_map_poi_fresh(stale, now=now, ttl_hours=24)
    assert not POIService.is_map_poi_fresh(None, now=now, ttl_hours=24)


def test_map_service_serializes_zero_coordinates_and_primary_image() -> None:
    property_obj = SimpleNamespace(
        id=7,
        title="测试房源",
        district="中心区",
        country="SG",
        address="1 Test Road",
        price_monthly=3200,
        bedrooms=1,
        bathrooms=1,
        property_type="studio",
        latitude=0,
        longitude=0,
        area_sqm=28,
        images=[
            SimpleNamespace(filename="secondary.jpg", is_primary=False),
            SimpleNamespace(filename="primary.jpg", is_primary=True),
        ],
    )

    payload = MapService.serialize_property(property_obj)
    assert payload["latitude"] == 0.0
    assert payload["longitude"] == 0.0
    assert payload["primary_image_url"] == "/api/v1/uploads/primary.jpg"


def test_scoring_service_is_authoritative_comparison_facade() -> None:
    metrics = [
        PropertyMetrics(property_id=1, price=3000, area=30, transit_meters=500, rating=4.2),
        PropertyMetrics(property_id=2, price=3600, area=45, transit_meters=900, rating=4.7),
    ]
    assert ScoringService.score_comparison(metrics, "commute") == compute_scores(metrics, "commute")



@pytest.mark.asyncio
async def test_commute_api_slot_gives_up_instead_of_queueing_forever(monkeypatch) -> None:
    """槽位排队必须有 deadline，否则地图 API 不可达时批量通勤会从秒级退化到分钟级。

    httpx 的 timeout 只从 client.get 开始计时，在信号量外面等多久都不算，
    所以这个上限只能由 _commute_api_slot 自己保证。
    """
    import asyncio

    from app.core.config import get_settings
    from app.services import commute_service

    get_settings.cache_clear()
    monkeypatch.setenv("COMMUTE_API_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("COMMUTE_API_QUEUE_TIMEOUT_SECONDS", "0.05")
    commute_service._api_semaphores.clear()

    try:
        holder_released = asyncio.Event()

        async def hold_slot() -> None:
            async with commute_service._commute_api_slot():
                await holder_released.wait()

        holder = asyncio.create_task(hold_slot())
        await asyncio.sleep(0)  # 让 holder 先拿到唯一的槽位

        with pytest.raises(asyncio.TimeoutError):
            async with commute_service._commute_api_slot():
                pass

        holder_released.set()
        await holder

        # 槽位在超时后没有被泄漏：holder 释放后应当能立刻再次获取
        async with commute_service._commute_api_slot():
            pass
    finally:
        holder_released.set()
        commute_service._api_semaphores.clear()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_map_poi_refresh_is_deduped_per_property(monkeypatch) -> None:
    """缓存过期瞬间的并发请求只应投递一个刷新任务。

    没有 single-flight 锁时，N 个并发请求 = N 个任务 × 每任务 9 次外部地图搜索。
    """
    from app.celery_app import celery_app
    from app.services.poi_service import POIService

    monkeypatch.setattr(celery_app.conf, "task_always_eager", False, raising=False)

    enqueued: list[int] = []

    class FakeTask:
        @staticmethod
        def delay(property_id: int) -> None:
            enqueued.append(property_id)

    monkeypatch.setattr(
        "app.tasks.poi_tasks.generate_map_pois_for_property", FakeTask, raising=False
    )

    locks: set[int] = set()

    async def fake_lock(property_id: int) -> bool:
        if property_id in locks:
            return False
        locks.add(property_id)
        return True

    monkeypatch.setattr(POIService, "_acquire_refresh_lock", staticmethod(fake_lock))

    for _ in range(5):
        await POIService._enqueue_map_poi_refresh(42)
    await POIService._enqueue_map_poi_refresh(43)

    assert enqueued == [42, 43], "同一房源的重复投递应被锁挡掉"


@pytest.mark.asyncio
async def test_map_poi_refresh_falls_through_when_lock_unavailable(monkeypatch) -> None:
    """Redis 不可用时不能因此停掉刷新——去重是优化，不是前置条件。"""
    from app.core.config import get_settings
    from app.services.poi_service import POIService

    get_settings.cache_clear()
    monkeypatch.setenv("REDIS_URL", "disabled://tests")
    try:
        assert await POIService._acquire_refresh_lock(1) is True
    finally:
        get_settings.cache_clear()

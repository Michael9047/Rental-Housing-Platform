"""通勤结果缓存服务 —— 按起终点逐条缓存，并在 Redis 不可用时静默降级。"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Iterable

from redis.asyncio import Redis as AsyncRedis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "commute:result:v1"
_RESULT_FIELDS = (
    "dist_km",
    "walk_min",
    "bike_min",
    "drive_min",
    "transit_min",
    "source",
    "transit_verified",
)


class CommuteCacheService:
    """Redis 通勤缓存；缓存故障不影响路线计算主流程。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis: AsyncRedis | None = None
        self._disabled = not self.settings.commute_cache_enabled

    async def _get_redis(self) -> AsyncRedis | None:
        if self._disabled:
            return None
        if self._redis is None:
            try:
                self._redis = AsyncRedis.from_url(
                    self.settings.redis_url,
                    decode_responses=False,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                )
            except Exception:
                self._disabled = True
                logger.debug("Redis 配置不可用，通勤缓存已降级关闭", exc_info=True)
                return None
        return self._redis

    def _routing_signature(self, country: str | None, city: str | None) -> str:
        """把路由上下文和可用引擎写入 key，配置 API Key 后不会命中旧兜底。"""
        normalized_country = (country or "auto").strip().upper()
        normalized_city = (city or "").strip().lower()
        raw = (
            f"country={normalized_country}|city={normalized_city}|"
            f"amap={bool(self.settings.amap_web_key)}|ors={bool(self.settings.ors_api_key)}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def build_key(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        *,
        country: str | None = None,
        city: str | None = None,
    ) -> str:
        """坐标保留 5 位小数（约米级），吸收无意义的浮点抖动。"""
        route_signature = self._routing_signature(country, city)
        coordinates = ":".join(
            f"{float(value):.5f}"
            for value in (origin_lat, origin_lng, dest_lat, dest_lng)
        )
        return f"{_CACHE_PREFIX}:{route_signature}:{coordinates}"

    def _has_configured_route_api(self) -> bool:
        return bool(self.settings.amap_web_key or self.settings.ors_api_key)

    @staticmethod
    def _decode(raw: bytes | str | None) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or any(field not in payload for field in _RESULT_FIELDS):
            return None
        return {field: payload[field] for field in _RESULT_FIELDS}

    async def get_many(
        self,
        origin_lat: float,
        origin_lng: float,
        destinations: Iterable[Any],
        *,
        country: str | None = None,
        city: str | None = None,
    ) -> dict[int | str, dict[str, Any]]:
        """批量 MGET；返回以当前请求 dest_id 为键的命中结果。"""
        destination_list = list(destinations)
        if not destination_list:
            return {}
        redis = await self._get_redis()
        if redis is None:
            return {}

        keys = [
            self.build_key(
                origin_lat,
                origin_lng,
                destination.lat,
                destination.lng,
                country=country,
                city=city,
            )
            for destination in destination_list
        ]
        try:
            raw_values = await redis.mget(keys)
        except Exception:
            logger.debug("读取通勤缓存失败，继续调用路线服务", exc_info=True)
            return {}

        hits: dict[int | str, dict[str, Any]] = {}
        for destination, raw in zip(destination_list, raw_values, strict=False):
            payload = self._decode(raw)
            if payload is None:
                continue
            # 有真实路线 API 时不长期复用兜底结果，让临时故障可以自动恢复。
            if payload["source"] == "haversine_fallback" and self._has_configured_route_api():
                continue
            hits[destination.dest_id] = payload
        return hits

    async def set_many(
        self,
        origin_lat: float,
        origin_lng: float,
        destinations: Iterable[Any],
        results: Iterable[Any],
        *,
        country: str | None = None,
        city: str | None = None,
    ) -> None:
        """把一次批量计算结果逐目的地写入 Redis，各条目独立过期。"""
        redis = await self._get_redis()
        if redis is None:
            return
        destination_by_id = {destination.dest_id: destination for destination in destinations}
        try:
            async with redis.pipeline(transaction=False) as pipeline:
                for result in results:
                    destination = destination_by_id.get(result.dest_id)
                    if destination is None:
                        continue
                    payload = {field: getattr(result, field) for field in _RESULT_FIELDS}
                    ttl = (
                        self.settings.commute_fallback_cache_ttl_seconds
                        if result.source == "haversine_fallback"
                        else self.settings.commute_cache_ttl_seconds
                    )
                    key = self.build_key(
                        origin_lat,
                        origin_lng,
                        destination.lat,
                        destination.lng,
                        country=country,
                        city=city,
                    )
                    pipeline.setex(key, max(1, ttl), json.dumps(payload, ensure_ascii=False))
                await pipeline.execute()
        except Exception:
            logger.debug("写入通勤缓存失败，不影响本次路线结果", exc_info=True)

    async def close(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        except Exception:
            logger.debug("关闭通勤缓存连接失败", exc_info=True)
        finally:
            self._redis = None

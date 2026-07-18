"""Embedding 缓存 —— 用 Redis 缓存文本→向量映射，避免多轮对话中重复编码。

Key 格式: emb:cache:v1:{sha256(text)[:16]}
TTL: 1 小时

使用方式（在 EmbeddingService.generate_embedding 中）:
    cache = EmbeddingCache(redis_url)
    cached = await cache.get_embedding(text)
    if cached:
        return cached
    vector = await _do_embed(text)
    await cache.store_embedding(text, vector)
    return vector
"""

from __future__ import annotations

import hashlib
import json
import logging

from redis.asyncio import Redis as AsyncRedis

logger = logging.getLogger(__name__)

# 缓存 key 前缀 + 版本（升级格式时改版本号即可全局失效）
CACHE_PREFIX = "emb:cache"
CACHE_VERSION = "v1"
DEFAULT_TTL = 3600  # 1 小时


class EmbeddingCache:
    """Redis 向量缓存：text → embedding vector。

    精确匹配（SHA256），不做语义去重。
    Redis 不可用时静默降级——所有操作返回 None / False，不抛异常。
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: AsyncRedis | None = None

    async def _get_redis(self) -> AsyncRedis | None:
        """懒连接 Redis，失败时返回 None"""
        if self._redis is not None:
            try:
                await self._redis.ping()
            except Exception:
                self._redis = None

        if self._redis is None:
            try:
                self._redis = AsyncRedis.from_url(
                    self._redis_url, decode_responses=False
                )
            except Exception:
                logger.debug("Redis 不可用，embedding 缓存禁用")
                return None
        return self._redis

    @staticmethod
    def _make_key(text: str) -> str:
        """SHA256 前 16 位作为缓存 key"""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"{CACHE_PREFIX}:{CACHE_VERSION}:{digest}"

    async def get_embedding(self, text: str) -> list[float] | None:
        """获取缓存的向量，未命中返回 None"""
        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            key = self._make_key(text)
            raw = await redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.debug("embedding 缓存读取失败", exc_info=True)
            return None

    async def store_embedding(
        self, text: str, vector: list[float], ttl: int = DEFAULT_TTL
    ) -> bool:
        """存储向量到缓存。返回 True 表示成功。"""
        redis = await self._get_redis()
        if redis is None:
            return False
        try:
            key = self._make_key(text)
            await redis.setex(key, ttl, json.dumps(vector))
            return True
        except Exception:
            logger.debug("embedding 缓存写入失败", exc_info=True)
            return False

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

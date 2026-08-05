from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.services.embedding_cache import EmbeddingCache

logger = logging.getLogger(__name__)


def _build_property_text(property_data: dict) -> str:
    parts = [
        property_data.get("title", ""),
        property_data.get("description") or "",
        property_data.get("address", ""),
        property_data.get("district", ""),
        property_data.get("property_type", "1-bed"),
    ]
    return " ".join(part for part in parts if part)


class EmbeddingService:
    """Embedding 生成服务。

    优先使用智谱 AI（OpenAI 兼容接口，成本更低），未配置时回退到 OpenAI。
    智谱 embedding-3 支持自定义输出维度，取 settings.embedding_dimensions（默认 1536）
    与 pgvector 列（UnitType.embedding）对齐，避免迁移/重新回填历史数据。

    性能：
    - 单例复用（见 get_embedding_service），内部 AsyncOpenAI 复用 httpx 连接池，
      避免每次请求新建 client。
    - Redis 文本→向量缓存（EmbeddingCache）：查询向量命中率高，省掉重复编码的网络往返与费用。
      Redis 不可用时静默降级，不影响主流程。
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._dimensions = settings.embedding_dimensions

        self._zhipu_client: AsyncOpenAI | None = None
        if settings.zhipu_api_key:
            self._zhipu_client = AsyncOpenAI(
                api_key=settings.zhipu_api_key,
                base_url=settings.zhipu_base_url,
                timeout=20.0,
                max_retries=1,
            )
        self._zhipu_model = settings.zhipu_embedding_model

        self._openai_client: AsyncOpenAI | None = None
        if settings.openai_api_key:
            self._openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=20.0,
                max_retries=1,
            )
        self._openai_model = settings.openai_embedding_model

        # 文本→向量缓存（懒连接，Redis 不可用时静默降级）
        redis_url = getattr(settings, "redis_url", "") or ""
        self._cache = EmbeddingCache(redis_url) if redis_url else None

    @property
    def is_available(self) -> bool:
        return self._zhipu_client is not None or self._openai_client is not None

    async def _do_embed(self, text: str) -> list[float]:
        """实际调用 Embedding API（不走缓存）。"""
        if self._zhipu_client is not None:
            response = await self._zhipu_client.embeddings.create(
                model=self._zhipu_model,
                input=text,
                dimensions=self._dimensions,
            )
            return response.data[0].embedding

        if self._openai_client is not None:
            response = await self._openai_client.embeddings.create(
                model=self._openai_model,
                input=text,
            )
            return response.data[0].embedding

        raise RuntimeError("未配置任何 Embedding API Key（ZHIPU_API_KEY 或 OPENAI_API_KEY）")

    async def generate_embedding(self, text: str) -> list[float]:
        """生成文本向量：先查 Redis 缓存，未命中再调 API 并回写。

        缓存 key 含 provider+维度，避免切换 provider 或维度后读到旧向量。
        """
        cache_key = f"{self._cache_namespace()}:{text}"
        if self._cache is not None:
            cached = await self._cache.get_embedding(cache_key)
            if cached is not None:
                return cached

        vector = await self._do_embed(text)
        # 回写缓存（失败静默，不影响主流程）
        if self._cache is not None:
            await self._cache.store_embedding(cache_key, vector)
        return vector

    def _cache_namespace(self) -> str:
        """缓存命名空间：provider + 维度，切换后自然失效。"""
        if self._zhipu_client is not None:
            return f"zhipu:{self._zhipu_model}:{self._dimensions}"
        return f"openai:{self._openai_model}"

    async def generate_property_embedding(self, property_data: dict) -> list[float]:
        text = _build_property_text(property_data)
        return await self.generate_embedding(text)


# ── 单例 ────────────────────────────────────────────────────────────
# 复用内部 AsyncOpenAI client 的 httpx 连接池与 Redis 连接，避免每请求新建。
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

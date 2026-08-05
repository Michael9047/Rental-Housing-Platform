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
    与 pgvector 列（Property.embedding）对齐，避免迁移/重新回填历史数据。

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
        # 用 getattr 容错：缓存是纯性能优化，缺 redis_url 配置时不应影响 embedding 主功能。
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

    async def _do_embed_many(self, texts: list[str]) -> list[list[float]]:
        """单次请求批量生成向量，并按输入顺序返回。"""
        if not texts:
            return []
        if self._zhipu_client is not None:
            response = await self._zhipu_client.embeddings.create(
                model=self._zhipu_model,
                input=texts,
                dimensions=self._dimensions,
            )
        elif self._openai_client is not None:
            response = await self._openai_client.embeddings.create(
                model=self._openai_model,
                input=texts,
            )
        else:
            raise RuntimeError("未配置任何 Embedding API Key（ZHIPU_API_KEY 或 OPENAI_API_KEY）")

        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(texts):
            raise RuntimeError(
                f"Embedding 批量响应数量不一致：请求 {len(texts)}，返回 {len(ordered)}"
            )
        return [item.embedding for item in ordered]

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

    async def generate_embeddings(
        self,
        texts: list[str],
        *,
        batch_size: int = 50,
    ) -> list[list[float]]:
        """批量生成文本向量，复用缓存并限制单次请求规模。"""
        if not texts:
            return []
        if batch_size < 1:
            raise ValueError("batch_size 必须大于 0")

        vectors: list[list[float] | None] = [None] * len(texts)
        missing_indexes: list[int] = []
        namespace = self._cache_namespace()
        for index, value in enumerate(texts):
            cache_key = f"{namespace}:{value}"
            cached = (
                await self._cache.get_embedding(cache_key)
                if self._cache is not None else None
            )
            if cached is None:
                missing_indexes.append(index)
            else:
                vectors[index] = cached

        for start in range(0, len(missing_indexes), batch_size):
            indexes = missing_indexes[start:start + batch_size]
            chunk_texts = [texts[index] for index in indexes]
            chunk_vectors = await self._do_embed_many(chunk_texts)
            for index, vector in zip(indexes, chunk_vectors):
                vectors[index] = vector
                if self._cache is not None:
                    await self._cache.store_embedding(
                        f"{namespace}:{texts[index]}",
                        vector,
                    )

        if any(vector is None for vector in vectors):
            raise RuntimeError("Embedding 批量生成存在缺失结果")
        return [vector for vector in vectors if vector is not None]

    def _cache_namespace(self) -> str:
        """缓存命名空间：provider + 维度，切换后自然失效。"""
        if self._zhipu_client is not None:
            return f"zhipu:{self._zhipu_model}:{self._dimensions}"
        return f"openai:{self._openai_model}"

    async def generate_property_embedding(self, property_data: dict) -> list[float]:
        text = _build_property_text(property_data)
        return await self.generate_embedding(text)

    async def close(self) -> None:
        """关闭缓存与 HTTP 客户端，供一次性脚本显式释放资源。"""
        if self._cache is not None:
            await self._cache.close()
        clients = [self._zhipu_client, self._openai_client]
        for client in clients:
            if client is not None:
                await client.close()


# ── 单例 ────────────────────────────────────────────────────────────
# 复用内部 AsyncOpenAI client 的 httpx 连接池与 Redis 连接，避免每请求新建。
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

from openai import AsyncOpenAI

from app.core.config import get_settings


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

    @property
    def is_available(self) -> bool:
        return self._zhipu_client is not None or self._openai_client is not None

    async def generate_embedding(self, text: str) -> list[float]:
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

    async def generate_property_embedding(self, property_data: dict) -> list[float]:
        text = _build_property_text(property_data)
        return await self.generate_embedding(text)

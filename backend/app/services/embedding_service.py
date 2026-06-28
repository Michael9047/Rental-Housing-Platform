from openai import AsyncOpenAI

from app.core.config import get_settings


def _build_property_text(property_data: dict) -> str:
    parts = [
        property_data.get("title", ""),
        property_data.get("description") or "",
        property_data.get("address", ""),
        property_data.get("district", ""),
        property_data.get("property_type", "apartment"),
    ]
    return " ".join(part for part in parts if part)


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model

    async def generate_embedding(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return response.data[0].embedding

    async def generate_property_embedding(self, property_data: dict) -> list[float]:
        text = _build_property_text(property_data)
        return await self.generate_embedding(text)
from unittest.mock import AsyncMock, patch

import pytest


class TestEmbeddingService:
    @pytest.mark.asyncio
    async def test_generate_embedding_returns_1536_dimensions(self) -> None:
        from app.services.embedding_service import EmbeddingService

        mock_embedding = [0.05] * 1536
        with patch(
            "app.services.embedding_service.AsyncOpenAI"
        ) as mock_client_class:
            mock_instance = AsyncMock()
            mock_embeddings = AsyncMock()
            mock_embeddings.create = AsyncMock(
                return_value=AsyncMock(
                    data=[AsyncMock(embedding=mock_embedding)]
                )
            )
            mock_instance.embeddings = mock_embeddings
            mock_client_class.return_value = mock_instance

            service = EmbeddingService()
            result = await service.generate_embedding("test text")

        assert len(result) == 1536
        assert result == mock_embedding

    @pytest.mark.asyncio
    async def test_build_property_text_combines_fields(self) -> None:
        from app.services.embedding_service import _build_property_text

        text = _build_property_text({
            "title": "Sunny Apartment",
            "description": "Near metro station",
            "address": "88 University Rd",
            "district": "SIP",
            "property_type": "apartment",
        })

        assert "Sunny Apartment" in text
        assert "Near metro station" in text
        assert "88 University Rd" in text
        assert "SIP" in text
        assert "apartment" in text

    @pytest.mark.asyncio
    async def test_build_property_text_skips_none_fields(self) -> None:
        from app.services.embedding_service import _build_property_text

        text = _build_property_text({
            "title": "Studio",
            "description": None,
            "address": "1 Main St",
            "district": "Gusu",
        })

        assert "None" not in text
        assert text == "Studio 1 Main St Gusu apartment"
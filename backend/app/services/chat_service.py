import json
import logging
import uuid
from typing import AsyncGenerator

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession, ChatSessionStatus
from app.models.property import Property

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._chat_model = settings.openai_chat_model

    # ── Session management ────────────────────────────────────────

    async def create_session(self, user_id: int, title: str | None = None) -> ChatSession:
        chat_session = ChatSession(
            user_id=user_id,
            session_id=uuid.uuid4().hex,
            title=title,
            status=ChatSessionStatus.active,
        )
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session

    async def get_session(self, session_id: int, user_id: int) -> ChatSession | None:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await self.session.scalars(stmt)
        return result.first()

    async def list_sessions(self, user_id: int) -> list[ChatSession]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def close_session(self, session_id: int, user_id: int) -> bool:
        chat_session = await self.get_session(session_id, user_id)
        if not chat_session:
            return False
        chat_session.status = ChatSessionStatus.closed
        chat_session.accumulated_filters = None  # 关闭时清空上下文记忆
        await self.session.commit()
        return True

    async def delete_session(self, session_id: int, user_id: int) -> bool:
        chat_session = await self.get_session(session_id, user_id)
        if not chat_session:
            return False
        await self.session.delete(chat_session)
        await self.session.commit()
        return True

    # ── Messages ──────────────────────────────────────────────────

    async def get_messages(self, session_id: int, user_id: int) -> list[ChatMessage]:
        chat_session = await self.get_session(session_id, user_id)
        if not chat_session:
            return []
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    # ── RAG context builder ───────────────────────────────────────

    async def _build_rag_context(self, query: str) -> tuple[str, list[dict]]:
        """Generate embedding for query, search pgvector, return context text + matched properties."""
        from sqlalchemy import Float

        from app.services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService()
        query_vec = await embedding_service.generate_embedding(query)

        # pgvector 的 L2 距离操作符（新版 pgvector 不再导出 l2_distance 函数）
        similarity_expr = (
            Property.embedding.op("<->", return_type=Float)(query_vec).label("similarity")
        )
        stmt = (
            select(Property, similarity_expr)
            .where(Property.embedding.isnot(None))
            .where(Property.status == "available")
            .order_by(similarity_expr)
            .limit(5)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        if not rows:
            return "", []

        properties_context = []
        matched = []

        for idx, (prop, sim) in enumerate(rows):
            parts = [
                f"房源 {idx + 1}:",
                f"标题: {prop.title}",
                f"区域: {prop.district}",
                f"地址: {prop.address}",
                f"月租: ¥{prop.price_monthly}",
                f"户型: {prop.bedrooms}室{prop.bathrooms}卫",
            ]
            if prop.area_sqm:
                parts.append(f"面积: {prop.area_sqm}㎡")
            if prop.description:
                parts.append(f"描述: {prop.description}")

            properties_context.append("\n".join(parts))

            matched.append({
                "id": prop.id,
                "title": prop.title,
                "district": prop.district,
                "address": prop.address,
                "price_monthly": float(prop.price_monthly),
                "bedrooms": prop.bedrooms,
                "bathrooms": prop.bathrooms,
                "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
                "property_type": prop.property_type.value,
                "similarity": round(float(sim), 4) if sim else None,
            })

        context = "\n\n".join(properties_context)
        return context, matched

    # ── Chat ──────────────────────────────────────────────────────

    SYSTEM_PROMPT = """你是一个专业的租房顾问助手。你的任务是根据用户的需求和系统匹配的房源信息，帮助用户找到合适的租房。

规则:
1. 如果系统提供了匹配的房源，请根据这些房源信息回答用户。引用具体的房源标题、价格和区域。
2. 如果系统没有匹配到房源，请礼貌地告知用户，并建议他们调整搜索条件（如扩大区域范围、调整预算等）。
3. 回答要简洁、友好，用中文。
4. 不要编造任何不存在的房源信息。
5. 如果用户的问题与租房无关，可以礼貌地引导回租房话题。"""

    def _build_messages(
        self,
        query: str,
        history: list[dict],
        rag_context: str,
    ) -> list[dict]:
        system_content = self.SYSTEM_PROMPT
        if rag_context:
            system_content += f"\n\n=== 当前匹配的房源信息 ===\n{rag_context}\n=== 房源信息结束 ==="

        messages = [{"role": "system", "content": system_content}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": query})
        return messages

    async def chat(
        self,
        session_id: int,
        user_id: int,
        query: str,
        history: list[dict] | None = None,
    ) -> dict:
        """Non-streaming chat: returns full response + matched properties."""
        chat_session = await self.get_session(session_id, user_id)
        if not chat_session:
            raise ValueError("Chat session not found")

        if history is None:
            history = []

        # Auto-title on first message
        if chat_session.title is None and not history:
            chat_session.title = query[:100]
            await self.session.commit()

        # Build RAG context
        rag_context, matched_properties = await self._build_rag_context(query)

        # Build messages
        messages = self._build_messages(query, history, rag_context)

        # Call OpenAI
        response = await self._client.chat.completions.create(
            model=self._chat_model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        reply_content = response.choices[0].message.content or ""

        # Save messages
        user_msg = ChatMessage(
            session_id=session_id,
            role=ChatMessageRole.user,
            content=query,
            metadata_={"search_params": {}},
        )
        assistant_msg = ChatMessage(
            session_id=session_id,
            role=ChatMessageRole.assistant,
            content=reply_content,
            metadata_={"matched_properties": matched_properties},
        )
        self.session.add_all([user_msg, assistant_msg])
        await self.session.commit()

        return {
            "reply": reply_content,
            "matched_properties": matched_properties,
        }

    async def chat_stream(
        self,
        session_id: int,
        user_id: int,
        query: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat: yields SSE-formatted chunks."""
        chat_session = await self.get_session(session_id, user_id)
        if not chat_session:
            yield f"data: {json.dumps({'error': 'Chat session not found'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        if history is None:
            history = []

        # Auto-title on first message
        if chat_session.title is None and not history:
            chat_session.title = query[:100]
            await self.session.commit()

        try:
            # Build RAG context
            rag_context, matched_properties = await self._build_rag_context(query)

            # Send matched properties first
            yield f"data: {json.dumps({'type': 'matched', 'properties': matched_properties})}\n\n"

            # Build messages
            messages = self._build_messages(query, history, rag_context)

            # Save user message
            user_msg = ChatMessage(
                session_id=session_id,
                role=ChatMessageRole.user,
                content=query,
                metadata_={"search_params": {}},
            )
            self.session.add(user_msg)
            await self.session.commit()

            # Stream response
            stream = await self._client.chat.completions.create(
                model=self._chat_model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                stream=True,
            )

            full_reply = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_reply += delta.content
                    yield f"data: {json.dumps({'type': 'content', 'content': delta.content})}\n\n"

            # Save assistant message
            assistant_msg = ChatMessage(
                session_id=session_id,
                role=ChatMessageRole.assistant,
                content=full_reply,
                metadata_={"matched_properties": matched_properties},
            )
            self.session.add(assistant_msg)
            await self.session.commit()

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as exc:
            logger.exception("Chat stream error: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

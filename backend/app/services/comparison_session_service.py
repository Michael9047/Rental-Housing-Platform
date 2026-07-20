"""对比 Agent 会话服务 —— 持久化 CompareSession / CompareMessage

仿 ChatService 的模式：create / get / add_message / history。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compare_session import (
    CompareMessage,
    CompareSession,
    CompareSessionStatus,
)

logger = logging.getLogger(__name__)


class ComparisonSessionService:
    """对比会话持久化"""

    def __init__(self, session: AsyncSession) -> None:
        self.db = session

    async def create_session(
        self,
        user_id: int,
        property_ids: list[int],
        priority: str = "balanced",
    ) -> CompareSession:
        sess = CompareSession(
            user_id=user_id,
            property_ids=property_ids,
            priority=priority,
            status=CompareSessionStatus.active,
        )
        self.db.add(sess)
        await self.db.commit()
        await self.db.refresh(sess)
        return sess

    async def get_session(
        self, session_id: int, user_id: int
    ) -> CompareSession | None:
        row = await self.db.execute(
            select(CompareSession).where(
                CompareSession.id == session_id,
                CompareSession.user_id == user_id,
            )
        )
        return row.scalar_one_or_none()

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str | None = None,
        tool_calls: dict | None = None,
    ) -> CompareMessage:
        msg = CompareMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def get_history(self, session_id: int) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(CompareMessage)
                .where(CompareMessage.session_id == session_id)
                .order_by(CompareMessage.created_at.asc())
            )
        ).scalars().all()
        return [
            {"role": m.role, "content": m.content, "tool_calls": m.tool_calls}
            for m in rows
        ]

    async def update_result_cache(
        self, session_id: int, result: dict[str, Any]
    ) -> None:
        sess = await self.db.get(CompareSession, session_id)
        if sess:
            sess.result_cache = result
            await self.db.commit()

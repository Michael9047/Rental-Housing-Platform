"""Agent 长期偏好服务 —— 复用 SavedSearch 持久化用户确认的筛选条件。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saved_search import SavedSearch


AGENT_MEMORY_NAME = "__agent_long_term_preferences__"


class AgentMemoryService:
    """用现有 saved_searches 表保存一份用户级 Agent 偏好。

    这是显式记忆：只有 PUT /agent/memory 会写入，普通聊天不会自动把一次性
    条件永久化。这样既复用 main 的数据结构，也避免新增一套配置表。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> SavedSearch | None:
        stmt = (
            select(SavedSearch)
            .where(
                SavedSearch.user_id == user_id,
                SavedSearch.name == AGENT_MEMORY_NAME,
            )
            .order_by(SavedSearch.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def read_filters(self, user_id: int) -> dict[str, Any]:
        row = await self.get(user_id)
        return dict(row.query_params or {}) if row is not None else {}

    async def save(
        self,
        user_id: int,
        preferences: dict[str, Any],
        *,
        replace: bool = False,
    ) -> SavedSearch:
        row = await self.get(user_id)
        if row is None:
            row = SavedSearch(
                user_id=user_id,
                name=AGENT_MEMORY_NAME,
                query_params={},
                notify_enabled=False,
            )
            self.session.add(row)

        merged = {} if replace else dict(row.query_params or {})
        for key, value in preferences.items():
            if value is None or value == "" or value == []:
                merged.pop(key, None)
            else:
                merged[key] = value
        row.query_params = merged
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def clear(self, user_id: int) -> None:
        await self.session.execute(
            delete(SavedSearch).where(
                SavedSearch.user_id == user_id,
                SavedSearch.name == AGENT_MEMORY_NAME,
            )
        )
        await self.session.commit()

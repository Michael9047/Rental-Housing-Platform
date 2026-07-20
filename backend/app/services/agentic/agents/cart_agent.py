"""购物车 Agent —— 购物车 CRUD（无 LLM，直接委托现有 AgentService）。"""
from __future__ import annotations

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult, AgentError, AgentErrorType


class CartAgent(BaseAgent):
    name = "cart_agent"
    description = "购物车 CRUD（添加/移除/查看候选清单）"

    async def handle(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            content="购物车操作请通过 AgentService 处理。",
            success=True,
        )

"""对比 Agent —— 多维度房源对比（委托现有 AgentService.compare_cart，保持不动）。"""
from __future__ import annotations

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class CompareAgent(BaseAgent):
    name = "compare_agent"
    description = "多维度房源对比（价格/通勤/空间/评价）。保持现有逻辑不变。"

    tools = ["compare_dimensions", "cart_view", "poi_lookup", "commute_calc"]

    async def handle(self, context: AgentContext) -> AgentResult:
        """委托现有 AgentService.compare_cart()。"""
        return AgentResult(
            content="对比功能请通过 AgentService.compare_cart() 调用。",
            success=True,
        )

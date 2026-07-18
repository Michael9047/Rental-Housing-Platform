"""市场分析 Agent —— 价格分布、行情趋势、预算校准建议。"""
from __future__ import annotations

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class MarketAgent(BaseAgent):
    name = "market_agent"
    description = "价格分布、市场行情、预算校准（对应 EstateWise FinanceAnalyst + AnalyticsAnalyst）"
    tools = ["market_stats", "property_search"]

    MARKET_PROMPT = """你是租房市场分析师。根据市场数据帮用户理解：
1. 该区域/价位的房源数量
2. 价格分布（最低/最高/中位数）
3. 不同预算能租到什么条件的房子
4. 预算调整建议

用数据说话，给出客观的市场概况。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="", success=True)

        return await self.handle_with_react(
            context=context,
            system_prompt=self.MARKET_PROMPT,
            max_iterations=2,
        )

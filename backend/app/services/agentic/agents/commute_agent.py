"""通勤分析 Agent —— 对应 EstateWise MapAnalystAgent。"""
from __future__ import annotations

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class CommuteAgent(BaseAgent):
    name = "commute_agent"
    description = "通勤时间/路线分析（对应 EstateWise MapAnalyst，复用现有 commute_service）"
    tools = ["commute_calc"]

    COMMUTE_PROMPT = """你是通勤分析专家。分析房源到学校/公司的交通便利性。
- 计算步行/公交/驾车的时间和距离
- 比较不同房源的交通便利性
- 标注是否需要换乘"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.COMMUTE_PROMPT, max_iterations=2)

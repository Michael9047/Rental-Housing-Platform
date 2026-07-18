"""POI 分析 Agent —— 周边设施评分（对应 EstateWise Lifestyle Concierge）。"""
from __future__ import annotations

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class POIAgent(BaseAgent):
    name = "poi_agent"
    description = "周边设施分析（对应 EstateWise MapAnalyst，复用现有 poi_service）"
    tools = ["poi_lookup"]

    POI_PROMPT = """你是周边设施分析专家。分析房源附近的：
- 超市/便利店数量和距离
- 餐馆/咖啡厅丰富度
- 公交/地铁站距离
- 健身房/公园等休闲设施
用评分 + 描述的方式呈现。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.POI_PROMPT, max_iterations=2)

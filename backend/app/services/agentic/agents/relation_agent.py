"""关系 Agent —— 房源-区域-POI 关系分析（对应 EstateWise GraphAnalystAgent）。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class RelationAgent(BaseAgent):
    name = "relation_agent"
    description = "房源-区域-POI 关系图分析（向量相似关系，对应 EstateWise GraphAnalyst）"
    tools = ["poi_lookup", "commute_calc"]

    RELATION_PROMPT = """你是房源关系分析师。分析房源之间的：
- 相似性（同区域/同价位/同户型）
- 互补性（不同区域但通勤时间相近）
- 替代关系"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.RELATION_PROMPT, max_iterations=2)

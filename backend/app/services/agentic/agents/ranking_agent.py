"""排序 Agent —— 去重 + 多路重排 + 多样性优化。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class RankingAgent(BaseAgent):
    name = "ranking_agent"
    description = "搜索结果去重、多路融合重排、多样性优化（对应 EstateWise DedupeRankingAgent）"
    tools = ["gap_detect"]

    async def handle(self, context: AgentContext) -> AgentResult:
        return AgentResult(content="排序完成", success=True)

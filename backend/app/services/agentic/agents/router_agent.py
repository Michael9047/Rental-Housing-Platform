"""路由 Agent —— fast vs agentic 路径决策（对应 EstateWise RouterAgent + routing-strategy）。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class RouterAgent(BaseAgent):
    name = "router_agent"
    description = "路由决策：fast（直接回复）vs agentic（DAG 编排）"

    async def handle(self, context: AgentContext) -> AgentResult:
        return AgentResult(content="fast", success=True)

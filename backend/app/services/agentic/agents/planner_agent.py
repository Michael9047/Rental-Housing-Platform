"""规划 Agent —— 复杂请求任务分解（对应 EstateWise PlannerAgent）。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class PlannerAgent(BaseAgent):
    name = "planner_agent"
    description = "任务分解：将复杂请求拆为可执行的 Agent DAG（对应 EstateWise PlannerAgent）"

    async def handle(self, context: AgentContext) -> AgentResult:
        return AgentResult(content="plan created", success=True)

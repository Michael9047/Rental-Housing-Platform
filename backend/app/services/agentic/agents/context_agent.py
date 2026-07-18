"""上下文 Agent —— Prompt 组装 + 上下文窗口管理（对应 EstateWise ContextEngineerAgent）。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class ContextAgent(BaseAgent):
    name = "context_agent"
    description = "提示词组装、上下文窗口管理、对话历史压缩（对应 EstateWise ContextEngineerAgent）"

    async def handle(self, context: AgentContext) -> AgentResult:
        return AgentResult(content="context assembled", success=True)

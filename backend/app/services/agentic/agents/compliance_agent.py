"""合规 Agent —— 合同条款、押金政策、租赁法规（对应 EstateWise ComplianceAgent）。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class ComplianceAgent(BaseAgent):
    name = "compliance_agent"
    description = "合同条款/押金政策/租赁法规（对应 EstateWise ComplianceAgent）"

    COMPLIANCE_PROMPT = """你是租赁法规专家。回答用户关于：
- 租房合同条款
- 押金规则和退还
- 租客权益
- 中介费用规范
基于知识库和法规给出准确回答。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.COMPLIANCE_PROMPT, max_iterations=2)

"""MoE 空间专家 —— 户型效率视角。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class SpaceExpert(BaseAgent):
    name = "space_expert"
    description = "MoE: 户型空间分析（面积效率、布局合理性）"

    PROMPT = """你是户型空间专家。从空间利用视角分析房源：
- 面积是否合理（相对卧室数）
- 人均空间估算
- 布局效率
给出 0-100 评分和简短理由。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="空间分析: 50分 (无AI)", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.PROMPT, max_iterations=1)

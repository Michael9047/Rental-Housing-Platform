"""MoE 通勤专家 —— 通勤便利性视角。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class CommuteExpert(BaseAgent):
    name = "commute_expert"
    description = "MoE: 通勤便利性分析"
    tools = ["commute_calc"]

    PROMPT = """你是通勤便利性专家。从交通视角分析房源：
- 到主要目的地（学校/公司）的时间
- 交通方式多样性（地铁/公交/步行）
- 是否需要换乘
给出 0-100 评分和简短理由。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="通勤分析: 50分 (无AI)", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.PROMPT, max_iterations=1)

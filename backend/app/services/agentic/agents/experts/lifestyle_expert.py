"""MoE 生活配套专家 —— 周边设施丰富度视角。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class LifestyleExpert(BaseAgent):
    name = "lifestyle_expert"
    description = "MoE: 生活配套分析（餐饮/购物/健身/娱乐）"
    tools = ["poi_lookup"]

    PROMPT = """你是生活配套专家。从生活便利视角分析房源：
- 周边餐饮丰富度
- 超市/便利店距离
- 健身房/公园等休闲设施
给出 0-100 评分和简短理由。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="配套分析: 50分 (无AI)", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.PROMPT, max_iterations=1)

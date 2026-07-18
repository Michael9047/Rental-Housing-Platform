"""MoE 价格专家 —— 价格合理性视角。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class PriceExpert(BaseAgent):
    name = "price_expert"
    description = "MoE: 价格合理性分析（预算匹配度、性价比、市场对比）"
    tools = ["market_stats"]

    PROMPT = """你是价格分析专家。从价格视角分析房源：
- 是否在用户预算范围内
- 与同区域同类房源的均价对比
- 性价比判断（面积/价格比）
给出 0-100 评分和简短理由。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="价格分析: 50分 (无AI)", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.PROMPT, max_iterations=1)

"""MoE 区域专家 —— 社区安全/氛围视角。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class AreaExpert(BaseAgent):
    name = "area_expert"
    description = "MoE: 区域分析（安全性、社区氛围、发展潜力）"
    tools = ["market_stats", "poi_lookup"]

    PROMPT = """你是区域分析专家。从社区视角分析房源所在区域：
- 安全性
- 社区氛围（学生区/家庭区/商业区）
- 周边环境和噪音
给出 0-100 评分和简短理由。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="区域分析: 50分 (无AI)", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.PROMPT, max_iterations=1)

"""MoE 融合 Agent —— 加权投票融合 5 个专家分析结果。"""
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult


class MergerAgent(BaseAgent):
    name = "merger_agent"
    description = "MoE: 加权综合 5 个专家视角 → 最终评价"

    MERGER_PROMPT = """你是综合分析专家。你收到了 5 个专家对同一批房源的分析结果。
每个专家从不同视角给出了 0-100 评分和理由。

请综合所有专家的意见，给出：
1. 每套房源的综合评分（0-100）
2. 各维度权重调整（哪个维度对这批房源更重要）
3. 最终推荐排序
4. 一句话总结推荐理由

输出 JSON 格式。"""

    async def handle(self, context: AgentContext) -> AgentResult:
        if not self.llm_service.is_available:
            return AgentResult(content="综合分析不可用", success=True)
        return await self.handle_with_react(context=context, system_prompt=self.MERGER_PROMPT, max_iterations=1)

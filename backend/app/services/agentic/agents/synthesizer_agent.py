"""合成 Agent —— 多 Agent 结果融合为自然语言回复。

参考 EstateWise Supervisor.synthesizeResponse() + SynthesizerAgent。
根据漏斗阶段调整回复语气和内容风格。
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import (
    AgentContext,
    AgentResult,
)

logger = logging.getLogger(__name__)


class SynthesizerAgent(BaseAgent):
    """回复合成 Agent。读取漏斗阶段，融合多 Agent 结果。

    阶段 → 语气映射：
    - explore: 市场概览语气，引导用户细化需求
    - calibrate: 比较性语气，帮用户理解价格与质量的对应关系
    - narrow: 分析性语气，对比区域差异
    - compare: 决策性语气，给出明确推荐
    - decide: 行动导向，引导下一步
    """

    name = "synthesizer_agent"
    description = "多 Agent 结果融合 + 漏斗阶段语调适配"

    STAGE_TONES: dict[str, str] = {
        "explore": "用户刚开始探索，用市场概览的语气。告诉他们这一带有多少房源、价格区间、户型分布。引导他们细化需求。",
        "calibrate": "用户正在调整预算/户型。比较不同价位的房源质量差异。帮他们理解一分钱一分货。",
        "narrow": "用户正在对比区域。分析不同地段的配套设施、通勤便利性、租金差异。",
        "compare": "用户正在对比具体房源。给出明确的推荐排序和理由。指出每套的优劣势。",
        "decide": "用户已经选定或接近决定。确认他们的选择。引导下一步：预约看房、签约流程。",
        "general": "简洁友好的闲聊风格。1-2 句话回应。",
    }

    async def handle(self, context: AgentContext) -> AgentResult:
        """合成回复。"""
        # 读取漏斗阶段
        stage = "explore"
        if context.search_state:
            s = getattr(context.search_state, "funnel_stage", "explore")
            stage = s.value if hasattr(s, "value") else str(s)

        tone = self.STAGE_TONES.get(stage, self.STAGE_TONES["general"])

        if not self.llm_service.is_available:
            return AgentResult(
                content="我是租房推荐助手。请告诉我您想找的地区、预算和户型，我来帮您推荐房源。",
                success=True,
            )

        try:
            prompt = f"""你是租房对话助手。{tone}
规则：
- 1-3 句话，简洁有力
- 不要展开长篇分析
- 不要编造房源信息
- 如果用户输入不完整，礼貌引导补充"""

            reply = await self.llm_service.complete_text(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context.user_message},
                ],
                max_tokens=300,
            )
            return AgentResult(content=reply.strip(), success=True)
        except Exception as exc:
            logger.warning("SynthesizerAgent LLM 失败: %s", exc)
            return AgentResult(
                content="抱歉，AI 服务暂时不可用。您可以尝试使用筛选功能来查找房源。",
                success=False,
            )

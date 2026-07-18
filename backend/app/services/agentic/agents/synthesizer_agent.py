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
        "explore": "用户刚开始探索。给一个市场快照：这一带有多少房源、价格区间、户型分布。引导用户细化条件（预算？通勤？独卫？），不要直接推具体房源。",
        "calibrate": "用户正在了解行情。解释不同价位的房源差异（便宜的远 vs 贵的近、合租 vs 单间）。帮用户建立预算预期。",
        "narrow": "用户已明确条件，在对比不同区域/房源。逐套分析匹配度，指出每套的差异化优势（通勤、设施、价格）。给出明确排序建议。",
        "compare": "用户在做最终决定。直接给出推荐排序和理由。指出每套的 trade-off（这套贵但近 vs 那套便宜但远）。语气果断，帮用户下决心。",
        "decide": "用户已接近决定。确认他们的选择，强调所选房源的优势。引导下一步：预约看房、联系房东、准备签约。",
        "general": "西交利物浦大学周边的租房顾问。用口语化中文，简洁友好。如果用户问的是平台使用问题，引导他们查看帮助中心。",
    }

    async def handle(self, context: AgentContext) -> AgentResult:
        """合成回复：按漏斗阶段选择语气，单次 LLM 调用。"""
        # 读取漏斗阶段
        stage = "explore"
        if context.search_state:
            s = getattr(context.search_state, "funnel_stage", "explore")
            stage = s.value if hasattr(s, "value") else str(s)

        tone = self.STAGE_TONES.get(stage, self.STAGE_TONES["general"])

        if not self.llm_service.is_available:
            return AgentResult(
                content="我是西交利物浦大学周边的租房助手。请告诉我你想找的区域、预算和户型，我帮你筛房源。",
                success=True,
            )

        try:
            prompt = f"""你是西交利物浦大学周边的租房顾问。{tone}

回复规则：
- 用口语化中文，1-3 句话，不要展开长篇分析
- 不要编造房源价格、位置、设施
- 如果用户输入不完整，礼貌引导补充（预算？区域？通勤要求？）
- 如果在对比房源，客观指出每套的优缺点
- 永远不要承诺"一定能租到"或保证房源可用"""

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

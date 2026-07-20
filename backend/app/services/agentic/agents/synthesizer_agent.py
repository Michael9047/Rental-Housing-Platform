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
        "explore": "用户刚开始探索。给市场快照：这一带有多少房源、价格区间。引导细化条件（预算？通勤？独卫？）。例如「学校周边单间1500-2500都有，合租800起。你预算多少？要独卫吗？」",
        "calibrate": "用户正在了解行情。解释价位差异（便宜=远/合租 vs 贵=近/独卫）。帮建立预算预期。例如「学校附近1500以内基本是合租，单间独卫要1800+，这是这边的行情」",
        "narrow": "用户已明确条件。逐套分析匹配度，突出差异化优势。给出明确排序。例如「这3套里公寓A通勤最近，公寓B价格最低但面积小，公寓C性价比居中——我个人推荐公寓A」",
        "compare": "用户在做最终决定。直接推荐+理由，指出每套 trade-off。语气果断。例如「果断公寓A。虽然贵了200，但每天多睡20分钟+独卫，值这个差价」",
        "decide": "用户已接近决定。确认选择+强调优势+引导下一步。例如「公寓A是对的！步行10分钟到校，楼下就有食堂和便利店。要预约看房吗？」",
        "general": "留学生租房顾问。口语化中文，简洁友好。例如「嗨！想在学校附近租房？告诉我预算和需求，我帮你筛～」",
    }

    async def handle(self, context: AgentContext) -> AgentResult:
        """合成回复：按漏斗阶段选择语气，单次 LLM 调用。"""
        stage = "explore"
        if context.search_state:
            s = getattr(context.search_state, "funnel_stage", "explore")
            stage = s.value if hasattr(s, "value") else str(s)

        tone = self.STAGE_TONES.get(stage, self.STAGE_TONES["general"])

        if not self.llm_service.is_available:
            return AgentResult(
                content="我是面向留学生的海外租房助手。请告诉我你想去的学校、预算和户型，我帮你筛房源。",
                success=True,
            )

        try:
            prompt = f"""你是面向留学生的海外租房顾问。{tone}

回复规则：
- 口语化中文，1-3 句话，像学长/学姐在给建议
- 不编造房源价格、位置、设施
- 用户输入不完整时礼貌引导（预算？学校？通勤？）
- 对比房源时客观指出每套优缺点和 trade-off
- 用「你」不是「您」，用「我觉得」不是「系统推荐」
- 不说"一定能租到"或保证房源可用"""

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
                content="抱歉，AI 服务暂时不可用。你可以试试筛选功能来找房源。",
                success=False,
            )

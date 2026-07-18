"""搜索 Agent —— EstateWise 多 Agent 系统的核心嫁接点。

使用 EstateWise 的 ReAct 模式进行多轮工具调用：
    Think → Act → Observe → Repeat → Reply

搜索流程：
    1. extract_filters: NL → 结构化条件
    2. property_search: 向量 + 结构化搜索（自动渐进放宽）
    3. score_properties: 确定性质量评分
    4. gap_detect: 分数断层检测
    5. (可选) poi_lookup / commute_calc: 补充周边信息
    6. 合成推荐回复

底层复用：
    - PropertyService.search() — 向量 + 结构化检索
    - _search_with_relaxation() — 渐进放宽
    - _score_properties() — 评分算法
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import (
    AgentContext,
    AgentResult,
)

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """房源搜索 Agent。核心嫁接点 —— 把 EstateWise 的 ReAct 模式用在房源搜索上。

    使用 EstateWise 风格的 ReAct 循环：
    Think: 分析用户需求
    Act: extract_filters → property_search → score_properties
    Observe: 检查结果质量，不够则放宽重搜
    Reply: 给出推荐
    """

    name = "search_agent"
    description = "房源搜索 + 渐进放宽 + 质量评分。EstateWise ReAct 模式。"
    tools = [
        "extract_filters",
        "property_search",
        "score_properties",
        "gap_detect",
        "safe_fallback_check",
        "query_rewrite",
        "poi_lookup",
        "commute_calc",
    ]

    SEARCH_SYSTEM_PROMPT = """你是西交利物浦大学周边的租房搜索专家。

工具使用流程：
1. extract_filters: 从用户消息中提取 district/price_min/price_max/bedrooms/property_type
2. property_search: 用提取的条件搜索房源
3. score_properties: 对搜索结果进行质量评分
4. 如果结果不足，用 query_rewrite 调整条件重新搜索

规则：
- 只推荐真实存在的房源（property_search 返回的结果）
- 搜索结果不足时，建议用户放宽条件（扩大区域、提高预算、去掉设施限制）
- 回复时标注房源价格、区域、户型、亮点
- 用口语化中文回复，2-3 句话即可"""

    async def handle(self, context: AgentContext) -> AgentResult:
        """搜索入口：使用 ReAct loop。"""
        return await self.handle_with_react(
            context=context,
            system_prompt=self.SEARCH_SYSTEM_PROMPT,
            max_iterations=4,
        )

    # ── 直接搜索（不使用 ReAct，给 Supervisor 调用的快捷方法） ──

    async def search_direct(
        self,
        message: str,
        filters: dict[str, Any] | None = None,
        session: Any = None,
    ) -> dict[str, Any]:
        """直接搜索（不用 ReAct loop）—— 路由走 fast path 时使用。

        复用现有 AgentService.recommend_properties() 的逻辑。
        """
        from app.services.agent_service import AgentService

        agent_svc = AgentService(session)
        result = await agent_svc.recommend_properties(message, filters)
        return result

"""Agent 注册中心 —— 应用启动时调用 register_all_agents() 注册全部 6 个 Agent。

每个 Agent 的元数据（name/capabilities/tools/fallback 等）集中在此定义。
AgentRegistry 根据这些元数据进行能力查找、路由和降级。
"""
from __future__ import annotations

import logging

from app.services.agentic.orchestration.agent_registry import AgentRegistry
from app.services.agentic.orchestration.types import (
    AgentDefinition,
    CostTier,
    ModelId,
)

logger = logging.getLogger(__name__)


def register_all_agents(registry: AgentRegistry) -> None:
    """注册全部 Agent 到 AgentRegistry。

    在 _handle_with_supervisor() 中按请求调用（确保 Agent 元数据始终可用）。
    重复注册同一个 id 会覆盖旧定义，所以幂等安全。
    """

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 1 — 核心搜索链路（3 个）：每次搜索请求都执行
    # ═══════════════════════════════════════════════════════════════════════

    registry.register(AgentDefinition(
        id="filter_agent",
        name="筛选条件提取 Agent",
        description="从自然语言中提取结构化筛选条件（district/price/bedrooms/type/amenities）",
        model_id=ModelId.LITE,
        capabilities=["filter", "extraction", "nlp"],
        tools=["extract_filters", "property_search", "query_rewrite"],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
    ))

    registry.register(AgentDefinition(
        id="search_agent",
        name="房源搜索 Agent",
        description="ReAct 搜索：提取筛选 → 多路检索 → 评分 → 间隙检测。同时负责通勤/POI/行情查询。",
        model_id=ModelId.STANDARD,
        capabilities=["search", "property", "recommendation", "commute", "poi", "market"],
        tools=[
            "extract_filters", "property_search", "score_properties",
            "gap_detect", "safe_fallback_check", "query_rewrite",
            "poi_lookup", "commute_calc", "market_stats",
        ],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=8000,
        timeout_ms=120_000,
        fallback_agent_id="synthesizer_agent",
    ))

    registry.register(AgentDefinition(
        id="synthesizer_agent",
        name="回复合成 Agent",
        description="融合多个 Agent 的分析结果为自然中文回复，按漏斗阶段适配语调",
        model_id=ModelId.STANDARD,
        capabilities=["synthesis", "reply", "formatting"],
        tools=["safe_fallback_check", "build_fallback_reply"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=4000,
        timeout_ms=60_000,
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 2 — 条件任务 Agent（1 个）：按意图触发
    # cart / faq 已降级为工具（CartService + agent_faq），不再注册为 Agent
    # ═══════════════════════════════════════════════════════════════════════

    registry.register(AgentDefinition(
        id="compare_agent",
        name="房源对比 Agent",
        description="多维度对比房源：价格/通勤/空间/评价，输出对比报告",
        model_id=ModelId.STANDARD,
        capabilities=["compare", "ranking", "analysis"],
        tools=["compare_dimensions", "cart_view"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=6000,
        timeout_ms=60_000,
        fallback_agent_id="synthesizer_agent",
    ))

    logger.info(
        "已注册 %d 个 Agent: %s",
        len(registry.list_all()),
        [a.id for a in registry.list_all()],
    )

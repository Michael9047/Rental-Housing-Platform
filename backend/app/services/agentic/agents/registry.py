"""Agent 注册中心 —— 应用启动时调用 register_all_agents() 注册全部 21 个 Agent。

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
    # Layer 1 — 路由与编排（3 个）
    # ═══════════════════════════════════════════════════════════════════════

    registry.register(AgentDefinition(
        id="router_agent",
        name="路由决策 Agent",
        description="根据分类信号决定走 fast path 还是 agentic pipeline",
        model_id=ModelId.LITE,
        capabilities=["routing", "classification"],
        tools=[],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
    ))

    registry.register(AgentDefinition(
        id="planner_agent",
        name="任务分解 Agent",
        description="将复杂用户请求分解为子任务，构建执行 DAG",
        model_id=ModelId.LITE,
        capabilities=["planning", "decomposition", "dag"],
        tools=[],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
    ))

    # Supervisor 本身不注册为 Agent（它直接编排）

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 2 — 核心任务 Agent（4 个）
    # ═══════════════════════════════════════════════════════════════════════

    registry.register(AgentDefinition(
        id="search_agent",
        name="房源搜索 Agent",
        description="ReAct 搜索：提取筛选 → 多路检索 → 评分 → 间隙检测。核心嫁接点。",
        model_id=ModelId.STANDARD,
        capabilities=["search", "property", "recommendation"],
        tools=[
            "extract_filters", "property_search", "score_properties",
            "gap_detect", "safe_fallback_check", "query_rewrite",
            "poi_lookup", "commute_calc",
        ],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=8000,
        timeout_ms=120_000,
        fallback_agent_id="synthesizer_agent",
    ))

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

    registry.register(AgentDefinition(
        id="cart_agent",
        name="购物车 Agent",
        description="候选清单管理：查看/添加/移除，委托现有 AgentService 购物车方法",
        model_id=ModelId.LITE,
        capabilities=["cart", "favorites"],
        tools=["cart_view", "cart_add", "cart_remove"],
        cost_tier=CostTier.LOW,
        max_token_budget=1000,
        timeout_ms=15_000,
    ))

    registry.register(AgentDefinition(
        id="faq_agent",
        name="FAQ Agent",
        description="FAQ 规则匹配：押金/合同/费用/预订流程等政策咨询",
        model_id=ModelId.LITE,
        capabilities=["faq", "policy", "help"],
        tools=["faq_match"],
        cost_tier=CostTier.LOW,
        max_token_budget=1000,
        timeout_ms=15_000,
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 3 — 分析 Agent（7 个）
    # ═══════════════════════════════════════════════════════════════════════

    registry.register(AgentDefinition(
        id="filter_agent",
        name="筛选条件提取 Agent",
        description="从自然语言中提取结构化筛选条件（district/price/bedrooms/type）",
        model_id=ModelId.LITE,
        capabilities=["filter", "extraction", "nlp"],
        tools=["extract_filters", "property_search", "query_rewrite"],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
    ))

    registry.register(AgentDefinition(
        id="market_agent",
        name="市场分析 Agent",
        description="价格分布、户型分布、区域概况，帮助用户校准预算预期",
        model_id=ModelId.STANDARD,
        capabilities=["market", "analysis", "statistics"],
        tools=["market_stats", "property_search"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=4000,
        timeout_ms=60_000,
        fallback_agent_id="synthesizer_agent",
    ))

    registry.register(AgentDefinition(
        id="commute_agent",
        name="通勤分析 Agent",
        description="计算房源到目的地的通勤距离和时间（步行/公交/驾车）",
        model_id=ModelId.STANDARD,
        capabilities=["commute", "transportation", "map"],
        tools=["commute_calc", "property_search"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=4000,
        timeout_ms=60_000,
        fallback_agent_id="synthesizer_agent",
    ))

    registry.register(AgentDefinition(
        id="poi_agent",
        name="周边设施 Agent",
        description="查询房源周边 POI（超市/餐馆/地铁/公交/健身房等），按丰富度评分",
        model_id=ModelId.STANDARD,
        capabilities=["poi", "amenities", "lifestyle"],
        tools=["poi_lookup", "property_search"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=4000,
        timeout_ms=60_000,
        fallback_agent_id="synthesizer_agent",
    ))

    registry.register(AgentDefinition(
        id="compliance_agent",
        name="合规分析 Agent",
        description="合同条款分析、租赁法规咨询（当前为占位 Agent，后续接入法规库）",
        model_id=ModelId.LITE,
        capabilities=["compliance", "legal", "contract"],
        tools=[],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
        fallback_agent_id="faq_agent",
    ))

    registry.register(AgentDefinition(
        id="ranking_agent",
        name="排序去重 Agent",
        description="搜索结果去重 + 质量排序 + 多样性注入",
        model_id=ModelId.LITE,
        capabilities=["ranking", "dedup", "diversity"],
        tools=["gap_detect"],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
    ))

    registry.register(AgentDefinition(
        id="relation_agent",
        name="房源关系 Agent",
        description="分析房源之间的相似性、替代关系、互补关系",
        model_id=ModelId.LITE,
        capabilities=["relation", "graph", "similarity"],
        tools=["property_search"],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 4 — MoE 专家组（7 个：6 专家 + 1 合并器）
    # ═══════════════════════════════════════════════════════════════════════

    registry.register(AgentDefinition(
        id="amenity_expert",
        name="设施硬约束专家",
        description="AND 语义设施检查：排除不满足硬约束的房源，纯 Python 逻辑不调用 LLM",
        model_id=ModelId.LITE,
        capabilities=["hard_filter", "amenity_check", "constraint_validation"],
        tools=[],  # 纯计算，不需要工具
        cost_tier=CostTier.LOW,
        max_token_budget=0,  # 无 LLM 调用
        timeout_ms=5_000,
    ))

    registry.register(AgentDefinition(
        id="price_expert",
        name="价格专家",
        description="分析房源价格的合理性、性价比、与市场均价的对比",
        model_id=ModelId.STANDARD,
        capabilities=["price", "budget", "value"],
        tools=["market_stats", "property_search"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=3000,
        timeout_ms=45_000,
    ))

    registry.register(AgentDefinition(
        id="commute_expert",
        name="通勤专家",
        description="分析房源的通勤便利程度（到学校/商圈/交通枢纽的时间）",
        model_id=ModelId.STANDARD,
        capabilities=["commute", "accessibility"],
        tools=["commute_calc"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=3000,
        timeout_ms=45_000,
    ))

    registry.register(AgentDefinition(
        id="lifestyle_expert",
        name="生活配套专家",
        description="分析房源周边的餐饮、购物、健身、娱乐等生活便利性",
        model_id=ModelId.STANDARD,
        capabilities=["lifestyle", "amenities", "entertainment"],
        tools=["poi_lookup"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=3000,
        timeout_ms=45_000,
    ))

    registry.register(AgentDefinition(
        id="space_expert",
        name="户型空间专家",
        description="分析房源的面积效率、户型合理性、空间利用率",
        model_id=ModelId.STANDARD,
        capabilities=["space", "layout", "efficiency"],
        tools=["property_search"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=3000,
        timeout_ms=45_000,
    ))

    registry.register(AgentDefinition(
        id="area_expert",
        name="区域分析专家",
        description="分析房源所在区域的安全性、社区氛围、发展规划",
        model_id=ModelId.STANDARD,
        capabilities=["area", "neighborhood", "safety"],
        tools=["market_stats", "poi_lookup"],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=3000,
        timeout_ms=45_000,
    ))

    registry.register(AgentDefinition(
        id="merger_agent",
        name="MoE 合并器",
        description="加权投票融合 5 位专家的分析结果，输出综合评分",
        model_id=ModelId.STANDARD,
        capabilities=["merging", "aggregation", "voting"],
        tools=[],
        cost_tier=CostTier.MEDIUM,
        max_token_budget=4000,
        timeout_ms=60_000,
        fallback_agent_id="synthesizer_agent",
    ))

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 5 — 响应合成（2 个）
    # ═══════════════════════════════════════════════════════════════════════

    registry.register(AgentDefinition(
        id="context_agent",
        name="上下文管理 Agent",
        description="管理对话上下文，追踪搜索漏斗状态变化",
        model_id=ModelId.LITE,
        capabilities=["context", "state", "memory"],
        tools=[],
        cost_tier=CostTier.LOW,
        max_token_budget=2000,
        timeout_ms=30_000,
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

    logger.info(
        "已注册 %d 个 Agent: %s",
        len(registry.list_all()),
        [a.id for a in registry.list_all()],
    )

"""执行 DAG —— 从 EstateWise supervisor.ts 的 ExecutionPlan 翻译。

ExecutionDAG 把分类结果转化为有依赖关系的 Agent 执行计划，
支持拓扑排序（同层可并行执行）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from .types import ExecutionMode, ExecutionPlan, ExecutionStep, TaskStatus


# ═══════════════════════════════════════════════════════════════════════════════
# Intent → DAG 映射规则
# ═══════════════════════════════════════════════════════════════════════════════

class Intent(str, Enum):
    SEARCH = "search"
    COMPARE = "compare"
    MANAGE_CART = "manage_cart"
    FAQ = "faq"
    GENERAL = "general"
    MARKET_ANALYSIS = "market_analysis"
    COMMUTE_INFO = "commute_info"
    POI_INFO = "poi_info"


# 每种 Intent 对应的 Agent DAG 模板
INTENT_DAG_TEMPLATES: dict[Intent, list[dict]] = {
    Intent.SEARCH: [
        {"agent_id": "filter_agent", "dependencies": [], "can_parallelize": False},
        {"agent_id": "search_agent", "dependencies": ["filter_agent"], "can_parallelize": False},
        {"agent_id": "synthesizer_agent", "dependencies": ["search_agent"], "can_parallelize": False},
    ],
    Intent.COMPARE: [
        {"agent_id": "compare_agent", "dependencies": [], "can_parallelize": False},
        {"agent_id": "synthesizer_agent", "dependencies": ["compare_agent"], "can_parallelize": False},
    ],
    Intent.MANAGE_CART: [
        {"agent_id": "cart_agent", "dependencies": [], "can_parallelize": False},
    ],
    Intent.FAQ: [
        {"agent_id": "faq_agent", "dependencies": [], "can_parallelize": False},
    ],
    Intent.GENERAL: [
        {"agent_id": "synthesizer_agent", "dependencies": [], "can_parallelize": False},
    ],
    Intent.MARKET_ANALYSIS: [
        {"agent_id": "filter_agent", "dependencies": [], "can_parallelize": False},
        {"agent_id": "search_agent", "dependencies": ["filter_agent"], "can_parallelize": False},
        {"agent_id": "market_agent", "dependencies": ["search_agent"], "can_parallelize": True},
        {"agent_id": "synthesizer_agent", "dependencies": ["search_agent", "market_agent"], "can_parallelize": False},
    ],
    Intent.COMMUTE_INFO: [
        {"agent_id": "commute_agent", "dependencies": [], "can_parallelize": False},
        {"agent_id": "synthesizer_agent", "dependencies": ["commute_agent"], "can_parallelize": False},
    ],
    Intent.POI_INFO: [
        {"agent_id": "poi_agent", "dependencies": [], "can_parallelize": False},
        {"agent_id": "synthesizer_agent", "dependencies": ["poi_agent"], "can_parallelize": False},
    ],
}

# 复杂搜索（需要 MoE 专家组的场景）
COMPLEX_SEARCH_DAG: list[dict] = [
    {"agent_id": "filter_agent", "dependencies": [], "can_parallelize": False},
    {"agent_id": "search_agent", "dependencies": ["filter_agent"], "can_parallelize": False},
    # 硬约束二次确认 —— 在软评分专家之前执行，做 AND 语义设施检查
    {"agent_id": "amenity_expert", "dependencies": ["search_agent", "filter_agent"], "can_parallelize": False},
    # MoE 专家组 — 5 个专家并行分析同一批房源（仅分析通过硬约束的候选）
    {"agent_id": "price_expert", "dependencies": ["amenity_expert"], "can_parallelize": True},
    {"agent_id": "commute_expert", "dependencies": ["amenity_expert"], "can_parallelize": True},
    {"agent_id": "lifestyle_expert", "dependencies": ["amenity_expert"], "can_parallelize": True},
    {"agent_id": "space_expert", "dependencies": ["amenity_expert"], "can_parallelize": True},
    {"agent_id": "area_expert", "dependencies": ["amenity_expert"], "can_parallelize": True},
    # 融合专家分析结果
    {"agent_id": "merger_agent", "dependencies": [
        "price_expert", "commute_expert", "lifestyle_expert", "space_expert", "area_expert"
    ], "can_parallelize": False},
    {"agent_id": "synthesizer_agent", "dependencies": ["search_agent", "merger_agent", "amenity_expert"], "can_parallelize": False},
]


# ═══════════════════════════════════════════════════════════════════════════════
# 执行 DAG
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExecutionNode:
    """DAG 中的一个节点。"""
    agent_name: str
    task_spec: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    priority: int = 0
    can_parallelize: bool = False


class ExecutionDAG:
    """Agent 执行 DAG。

    参考 EstateWise Supervisor.buildExecutionPlan()：
    - 从 Intent → 选择 DAG 模板
    - 拓扑排序（同层可并行）
    - 复杂度 > 0.6 时使用复杂搜索 DAG（含 MoE）
    """

    def __init__(self, nodes: list[ExecutionNode] | None = None) -> None:
        self.nodes: list[ExecutionNode] = nodes or []

    def add_node(self, node: ExecutionNode) -> None:
        self.nodes.append(node)

    def topological_sort(self) -> list[list[ExecutionNode]]:
        """拓扑排序，返回层级列表。同层节点可并行执行。

        参考 EstateWise Supervisor.topologicalLevels()。
        如果存在循环依赖，剩余节点放在最后一层（安全兜底）。
        """
        levels: list[list[ExecutionNode]] = []
        resolved: set[str] = set()
        remaining = list(self.nodes)

        # 给每个节点分配一个虚拟 ID（用 agent_name 作为标识）
        node_ids = {n.agent_name: n for n in self.nodes}

        while remaining:
            current_level: list[ExecutionNode] = []
            next_remaining: list[ExecutionNode] = []
            newly_resolved: set[str] = set()

            for node in remaining:
                deps_resolved = all(
                    dep in resolved
                    for dep in node.depends_on
                )
                if deps_resolved:
                    current_level.append(node)
                    newly_resolved.add(node.agent_name)
                else:
                    next_remaining.append(node)

            # 安全：如果本层为空（循环依赖），把剩余节点全放入最后一层
            if not current_level:
                levels.append(next_remaining)
                break

            # 本层全部收集完后统一标记为已解析（避免同层内串联依赖）
            resolved |= newly_resolved
            levels.append(current_level)
            remaining = next_remaining

        return levels

    def to_execution_plan(
        self,
        intent: str,
        task_description: str = "",
        mode: ExecutionMode = ExecutionMode.AGENTIC,
    ) -> ExecutionPlan:
        """将 DAG 转为 ExecutionPlan。"""
        plan_id = uuid.uuid4().hex[:12]
        steps: list[ExecutionStep] = []

        for i, node in enumerate(self.nodes):
            step_id = uuid.uuid4().hex[:12]
            steps.append(ExecutionStep(
                step_id=step_id,
                agent_id=node.agent_name,
                task_description=node.task_spec.get("description", task_description),
                dependencies=node.depends_on,
                priority=len(self.nodes) - i,
                optional=i > 0,  # 只有第一个 Agent 是必需的
            ))

        return ExecutionPlan(
            plan_id=plan_id,
            intent=intent,
            mode=mode,
            steps=steps,
            total_estimated_cost_usd=0.0,
            total_estimated_duration_ms=0.0,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 工厂方法
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def from_intent(
        intent: str,
        complexity: float = 0.5,
        enable_moe: bool = True,
    ) -> ExecutionDAG:
        """根据 Intent + 复杂度构建 DAG。

        Args:
            intent: 意图名称（search/compare/faq/general/...）
            complexity: 复杂度 0-1（> 0.6 触发复杂搜索 DAG）
            enable_moe: 是否启用 MoE 专家组
        """
        # 复杂搜索 → 使用 MoE DAG
        if intent == "search" and complexity > 0.6 and enable_moe:
            template = COMPLEX_SEARCH_DAG
        else:
            try:
                intent_enum = Intent(intent)
                template = INTENT_DAG_TEMPLATES.get(intent_enum, INTENT_DAG_TEMPLATES[Intent.GENERAL])
            except ValueError:
                template = INTENT_DAG_TEMPLATES[Intent.GENERAL]

        nodes = [
            ExecutionNode(
                agent_name=item["agent_id"],
                depends_on=item["dependencies"],
                can_parallelize=item.get("can_parallelize", False),
            )
            for item in template
        ]

        return ExecutionDAG(nodes=nodes)

    @staticmethod
    def from_classification(classification: dict) -> ExecutionDAG:
        """从 AgentService.classify_message() 的分类结果构建 DAG。

        Args:
            classification: {intent, sub_intent, complexity, routing, ...}
        """
        intent = classification.get("intent", "general")
        complexity = classification.get("complexity", 0.3)
        return ExecutionDAG.from_intent(intent, complexity)

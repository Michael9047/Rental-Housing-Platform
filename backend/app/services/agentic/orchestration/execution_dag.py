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
    GENERAL = "general"


# Intent → Agent 链路模板
# cart/faq 已降级为工具，不走 DAG，由 Supervisor 直接分发到工具层
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
    Intent.GENERAL: [
        {"agent_id": "synthesizer_agent", "dependencies": [], "can_parallelize": False},
    ],
}


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
        """根据 Intent 构建 DAG。

        Args:
            intent: 意图名称（search/compare/manage_cart/faq/general）
            complexity: 保留参数（兼容旧调用方，不再影响 DAG 选择）
            enable_moe: 保留参数（兼容旧调用方）
        """
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

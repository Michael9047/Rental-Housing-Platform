"""路由策略 —— 从 EstateWise routing-strategy.ts 翻译。

5 信号加权路由决策：tool_count / intent_confidence / conversation_depth
/ data_dependencies / ambiguity_level → "fast" 或 "agentic"
"""
from __future__ import annotations

from .types import ExecutionMode, RoutingDecision, RoutingSignals

# ═══════════════════════════════════════════════════════════════════════════════
# 默认权重（与 EstateWise 保持一致）
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_WEIGHTS = {
    "tool_count": 0.30,
    "intent_confidence": -0.20,  # 负权重：置信度越高，越不需要复杂的 agentic 路径
    "conversation_depth": 0.10,
    "data_dependencies": 0.25,
    "ambiguity_level": 0.15,
}

# 超过此阈值走 agentic 路径
AGENTIC_THRESHOLD = 0.45


class RoutingStrategy:
    """5 信号加权路由决策器。

    参考 EstateWise RoutingStrategy：
    - 评估 tool_count / confidence / depth / dependencies / ambiguity
    - score >= AGENTIC_THRESHOLD → agentic（DAG 编排）
    - score < AGENTIC_THRESHOLD → single_turn（直接回复）
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        threshold: float | None = None,
    ) -> None:
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.threshold = threshold or AGENTIC_THRESHOLD

    def evaluate(self, signals: RoutingSignals) -> RoutingDecision:
        """评估路由信号，返回路由决策。"""
        # 归一化每个信号到 [0, 1]
        normalized = {
            "tool_count": min(signals.tool_count / 5, 1.0),
            "intent_confidence": signals.intent_confidence,
            "conversation_depth": min(signals.conversation_depth / 10, 1.0),
            "data_dependencies": min(signals.data_dependencies / 4, 1.0),
            "ambiguity_level": signals.ambiguity_level,
        }

        # 计算加权分数
        breakdown: dict[str, float] = {}
        score = 0.0
        for key in self.weights:
            contribution = normalized.get(key, 0.0) * self.weights[key]
            breakdown[key] = round(contribution, 4)
            score += contribution

        # 钳制到 [0, 1]
        score = max(0.0, min(1.0, score))

        mode = ExecutionMode.AGENTIC if score >= self.threshold else ExecutionMode.SINGLE_TURN

        return RoutingDecision(
            mode=mode,
            score=round(score, 4),
            threshold=self.threshold,
            breakdown=breakdown,
        )

    @staticmethod
    def from_classification(classification: dict) -> RoutingSignals:
        """从分类结果提取路由信号。

        Args:
            classification: AgentService.classify_message() 或 Supervisor 的分类结果
        """
        intent = classification.get("intent", "general")
        sub_intent = classification.get("sub_intent", "")
        complexity = classification.get("complexity", 0.3)

        # 估算 tool_count（哪些 Agent 需要工具调用）
        tool_count = 1  # 默认至少 1 个工具
        if intent == "search":
            if sub_intent in ("explore", "browse"):
                tool_count = 3  # extract_filters + property_search + score
            elif sub_intent == "detail":
                tool_count = 4  # + poi_lookup + commute_calc
            elif sub_intent == "commute":
                tool_count = 2
        elif intent == "compare":
            tool_count = 3  # cart_view + compare_dimensions + poi_lookup
        elif intent == "manage_cart":
            tool_count = 1
        elif intent == "faq":
            tool_count = 0  # 纯规则，不需要工具

        # 估算 data_dependencies
        data_dependencies = 1
        if intent == "search" and sub_intent in ("browse", "explore"):
            data_dependencies = 2  # 需要 filters + search results
        elif intent == "compare":
            data_dependencies = 3  # 需要 cart + poi + commute

        return RoutingSignals(
            tool_count=tool_count,
            intent_confidence=classification.get("confidence", 0.5),
            conversation_depth=0,  # 由 Supervisor 在对话上下文中填充
            data_dependencies=data_dependencies,
            ambiguity_level=round(1.0 - classification.get("confidence", 0.5), 2),
        )

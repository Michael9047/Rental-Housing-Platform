"""编排引擎类型系统 —— 从 EstateWise types.ts 翻译为 Python。

覆盖：Agent 错误、模型配置、Agent 定义、任务生命周期、
      Handoff 协议、对话状态、执行计划、熔断器、追踪。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 错误类型
# ═══════════════════════════════════════════════════════════════════════════════

class AgentErrorType(str, Enum):
    RATE_LIMITED = "RATE_LIMITED"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    TOOL_FAILURE = "TOOL_FAILURE"
    HALLUCINATION_DETECTED = "HALLUCINATION_DETECTED"
    TIMEOUT = "TIMEOUT"
    MODEL_REFUSAL = "MODEL_REFUSAL"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CIRCULAR_HANDOFF = "CIRCULAR_HANDOFF"
    MAX_ITERATIONS_EXCEEDED = "MAX_ITERATIONS_EXCEEDED"
    EXTERNAL_API_FAILURE = "EXTERNAL_API_FAILURE"


class AgentError(Exception):
    """结构化 Agent 错误，对应 EstateWise AgentError。"""

    def __init__(
        self,
        type_: AgentErrorType,
        message: str,
        agent_id: str,
        recoverable: bool = True,
        metadata: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.type = type_
        self.agent_id = agent_id
        self.recoverable = recoverable
        self.metadata = metadata or {}
        self.cause = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": "AgentError",
            "type": self.type.value,
            "message": str(self),
            "agent_id": self.agent_id,
            "recoverable": self.recoverable,
            "metadata": self.metadata,
            "cause": str(self.cause) if self.cause else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 模型配置
# ═══════════════════════════════════════════════════════════════════════════════

class ModelId(str, Enum):
    """支持的模型等级。映射到 EstateWise 的 opus/sonnet/haiku 分层。"""
    PREMIUM = "premium"   # DeepSeek-V3 / Claude Opus
    STANDARD = "standard" # DeepSeek-V3 / Claude Sonnet
    LITE = "lite"         # DeepSeek-V3 (低成本模式) / Claude Haiku


@dataclass
class ModelConfig:
    api_model_id: str
    context_window: int
    max_output: int
    input_cost_per_1m: float
    output_cost_per_1m: float

    # 我们的模型体系（DeepSeek 为主，OpenAI fallback）
    @staticmethod
    def for_model_id(model_id: ModelId) -> ModelConfig:
        configs = {
            ModelId.PREMIUM: ModelConfig(
                api_model_id="deepseek-chat",  # 实际用统一模型，等级仅控制 token 预算
                context_window=128_000,
                max_output=16_000,
                input_cost_per_1m=0.27,
                output_cost_per_1m=1.10,
            ),
            ModelId.STANDARD: ModelConfig(
                api_model_id="deepseek-chat",
                context_window=128_000,
                max_output=8_000,
                input_cost_per_1m=0.27,
                output_cost_per_1m=1.10,
            ),
            ModelId.LITE: ModelConfig(
                api_model_id="deepseek-chat",
                context_window=128_000,
                max_output=4_000,
                input_cost_per_1m=0.27,
                output_cost_per_1m=1.10,
            ),
        }
        return configs[model_id]


# ═══════════════════════════════════════════════════════════════════════════════
# 任务生命周期
# ═══════════════════════════════════════════════════════════════════════════════

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class TaskMetadata:
    task_id: str
    agent_id: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    attempt: int = 1
    parent_task_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error_type: str | None = None
    error_message: str | None = None


@dataclass
class ToolCallRecord:
    tool_name: str
    input: dict[str, Any]
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class TaskResult:
    success: bool
    metadata: TaskMetadata
    data: Any = None
    error: AgentError | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    trace_span_id: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# 执行计划 (DAG)
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionMode(str, Enum):
    SINGLE_TURN = "single_turn"
    AGENTIC = "agentic"


@dataclass
class ExecutionStep:
    step_id: str
    agent_id: str
    task_description: str
    dependencies: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    estimated_duration_ms: float = 0.0
    priority: int = 0
    optional: bool = False
    status: TaskStatus = TaskStatus.PENDING
    result: TaskResult | None = None


@dataclass
class ExecutionPlan:
    plan_id: str
    intent: str
    mode: ExecutionMode
    steps: list[ExecutionStep] = field(default_factory=list)
    total_estimated_cost_usd: float = 0.0
    total_estimated_duration_ms: float = 0.0
    created_at: float = field(default_factory=time.time)
    budget_limit_usd: float | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 定义
# ═══════════════════════════════════════════════════════════════════════════════

class CostTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PREMIUM = "premium"


@dataclass
class AgentCapability:
    """Agent 能力声明 —— 用于 AgentRegistry 的查找匹配。"""
    name: str
    description: str
    intents: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)      # 漏斗阶段
    dependencies: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)


@dataclass
class AgentDefinition:
    id: str
    name: str
    description: str
    model_id: ModelId = ModelId.STANDARD
    system_prompt: str = ""
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    cost_tier: CostTier = CostTier.MEDIUM
    max_token_budget: int = 8000
    timeout_ms: int = 120_000
    fallback_agent_id: str | None = None
    tags: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Handoff 协议
# ═══════════════════════════════════════════════════════════════════════════════

class HandoffType(str, Enum):
    DELEGATION = "delegation"
    ESCALATION = "escalation"
    FALLBACK = "fallback"
    SPECIALIZATION = "specialization"
    REVIEW = "review"


@dataclass
class HandoffPayload:
    type: HandoffType
    from_agent_id: str
    to_agent_id: str
    task_description: str
    context: dict[str, Any] = field(default_factory=dict)
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    depth: int = 0
    chain_id: str = ""
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════════════════
# 对话状态
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ConversationMessage:
    role: str  # user | assistant | system | tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: float = field(default_factory=time.time)
    token_count: int | None = None


@dataclass
class ConversationState:
    messages: list[ConversationMessage] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 128_000
    turn_count: int = 0
    last_activity_at: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════════════════
# 路由信号
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RoutingSignals:
    tool_count: int = 0
    intent_confidence: float = 0.5
    conversation_depth: int = 0
    data_dependencies: int = 0
    ambiguity_level: float = 0.0


@dataclass
class RoutingDecision:
    mode: ExecutionMode
    score: float
    threshold: float
    breakdown: dict[str, float] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 熔断器
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    reset_timeout_ms: int = 60_000
    half_open_max_attempts: int = 1
    monitor_window_ms: int = 120_000


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 上下文（传递给每个 Agent 的标准上下文）
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentContext:
    """每个 Agent.handle() 接收的标准上下文。"""
    user_message: str
    history: list[dict[str, Any]] = field(default_factory=list)
    filters: dict[str, Any] | None = None
    user_id: int | None = None
    search_state: Any = None  # SearchState（避免循环导入）
    conversation_state: ConversationState | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Agent.handle() 返回的标准结果。"""
    content: str
    success: bool = True
    data: Any = None
    error: AgentError | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    context_updates: dict[str, Any] = field(default_factory=dict)

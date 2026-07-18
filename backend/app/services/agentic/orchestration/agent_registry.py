"""熔断器 + Agent 注册表 —— 从 EstateWise agent-registry.ts 翻译。

提供：
- CircuitBreaker：CLOSED / OPEN / HALF_OPEN 三态熔断
- AgentRegistry：中央 Agent 目录，含健康追踪、能力查找、降级链
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .types import (
    AgentCapability,
    AgentDefinition,
    AgentError,
    AgentErrorType,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CostTier,
    ModelId,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 熔断器
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """单 Agent 熔断器，实现 CLOSED / OPEN / HALF_OPEN 三态。

    参考 EstateWise CircuitBreaker：
    - CLOSED：正常通行，累计失败次数
    - OPEN：拒绝所有请求，等待 reset_timeout
    - HALF_OPEN：允许少量试探请求，成功则恢复 CLOSED，失败则回 OPEN
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_at = 0.0
        self._half_open_attempts = 0

    @property
    def state(self) -> CircuitBreakerState:
        if self._state == CircuitBreakerState.OPEN:
            elapsed_ms = (time.time() - self._last_failure_at) * 1000
            if elapsed_ms >= self.config.reset_timeout_ms:
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_attempts = 0
        return self._state

    def is_allowed(self) -> bool:
        current = self.state
        if current == CircuitBreakerState.CLOSED:
            return True
        if current == CircuitBreakerState.HALF_OPEN:
            return self._half_open_attempts < self.config.half_open_max_attempts
        return False

    def record_success(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._half_open_attempts = 0
        self._success_count += 1

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_at = time.time()

        if self._state == CircuitBreakerState.HALF_OPEN:
            self._half_open_attempts += 1
            self._state = CircuitBreakerState.OPEN
            return

        if self._failure_count >= self.config.failure_threshold:
            self._state = CircuitBreakerState.OPEN

    def reset(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_attempts = 0
        self._last_failure_at = 0.0

    @property
    def failure_count(self) -> int:
        return self._failure_count


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 注册表
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentMetrics:
    agent_id: str = ""
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_latency_ms: float = 0.0
    average_cost_usd: float = 0.0
    p95_latency_ms: float = 0.0
    last_request_at: float = 0.0
    circuit_breaker_state: str = "CLOSED"
    error_rate_percent: float = 0.0
    uptime_percent: float = 100.0


class AgentRegistry:
    """中央 Agent 注册表。参考 EstateWise AgentRegistry。

    功能：
    - Agent CRUD（注册/注销/查询）
    - 能力查找（按 capability 匹配 Agent）
    - 健康追踪 + 熔断器
    - 降级链解析（fallback chain）
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._metrics: dict[str, AgentMetrics] = {}
        self._latencies: dict[str, list[float]] = {}

    # ── CRUD ────────────────────────────────────────────────────────────

    def register(self, agent: AgentDefinition) -> None:
        self._agents[agent.id] = agent
        if agent.id not in self._breakers:
            self._breakers[agent.id] = CircuitBreaker()
        if agent.id not in self._metrics:
            self._metrics[agent.id] = AgentMetrics(agent_id=agent.id)
        if agent.id not in self._latencies:
            self._latencies[agent.id] = []

    def deregister(self, agent_id: str) -> bool:
        self._breakers.pop(agent_id, None)
        self._metrics.pop(agent_id, None)
        self._latencies.pop(agent_id, None)
        return self._agents.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> AgentDefinition | None:
        return self._agents.get(agent_id)

    def get_or_raise(self, agent_id: str) -> AgentDefinition:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentError(
                type_=AgentErrorType.DEPENDENCY_FAILURE,
                message=f'Agent "{agent_id}" 未注册',
                agent_id=agent_id,
                recoverable=False,
            )
        return agent

    def list_all(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    # ── 能力查找 ────────────────────────────────────────────────────────

    def find_by_capability(self, capability: str) -> list[AgentDefinition]:
        """按能力关键词模糊匹配。"""
        cap_lower = capability.lower()
        return [
            a for a in self._agents.values()
            if any(cap_lower in c.lower() for c in a.capabilities)
        ]

    def find_best_for_task(
        self,
        capability: str,
        preferred_tier: CostTier | None = None,
    ) -> AgentDefinition | None:
        """为任务找最佳 Agent：健康 + 匹配能力 + 成本优先。"""
        candidates = [
            a for a in self.find_by_capability(capability)
            if self.is_healthy(a.id)
        ]
        if not candidates:
            return None

        if preferred_tier:
            tier_match = next((a for a in candidates if a.cost_tier == preferred_tier), None)
            if tier_match:
                return tier_match

        # 按成本排序，取最便宜的
        candidates.sort(key=lambda a: a.model_id.value)
        return candidates[0]

    # ── 健康检查 ────────────────────────────────────────────────────────

    def is_healthy(self, agent_id: str) -> bool:
        breaker = self._breakers.get(agent_id)
        return breaker.is_allowed() if breaker else False

    def get_circuit_breaker_state(self, agent_id: str) -> CircuitBreakerState:
        breaker = self._breakers.get(agent_id)
        return breaker.state if breaker else CircuitBreakerState.OPEN

    def record_success(self, agent_id: str, latency_ms: float, cost_usd: float) -> None:
        breaker = self._breakers.get(agent_id)
        if breaker:
            breaker.record_success()

        m = self._metrics.get(agent_id)
        if m:
            m.total_requests += 1
            m.success_count += 1
            m.last_request_at = time.time()
            m.average_cost_usd = self._running_avg(
                m.average_cost_usd, cost_usd, m.total_requests
            )
            lats = self._latencies.setdefault(agent_id, [])
            lats.append(latency_ms)
            if len(lats) > 100:
                lats.pop(0)

            m.average_latency_ms = sum(lats) / len(lats) if lats else 0
            m.p95_latency_ms = self._percentile(lats, 0.95) if lats else 0
            m.error_rate_percent = (m.failure_count / m.total_requests * 100) if m.total_requests > 0 else 0
            m.uptime_percent = (m.success_count / m.total_requests * 100) if m.total_requests > 0 else 100
            m.circuit_breaker_state = self.get_circuit_breaker_state(agent_id).value

    def record_failure(self, agent_id: str, latency_ms: float) -> None:
        breaker = self._breakers.get(agent_id)
        if breaker:
            breaker.record_failure()

        m = self._metrics.get(agent_id)
        if m:
            m.total_requests += 1
            m.failure_count += 1
            m.last_request_at = time.time()
            lats = self._latencies.setdefault(agent_id, [])
            lats.append(latency_ms)
            if len(lats) > 100:
                lats.pop(0)
            m.average_latency_ms = sum(lats) / len(lats) if lats else 0
            m.p95_latency_ms = self._percentile(lats, 0.95) if lats else 0
            m.error_rate_percent = (m.failure_count / m.total_requests * 100) if m.total_requests > 0 else 0
            m.circuit_breaker_state = self.get_circuit_breaker_state(agent_id).value

    # ── 降级链 ──────────────────────────────────────────────────────────

    def resolve_fallback_chain(self, agent_id: str, max_depth: int = 3) -> list[AgentDefinition]:
        chain: list[AgentDefinition] = []
        visited: set[str] = set()
        current_id: str | None = agent_id

        while current_id and len(chain) < max_depth and current_id not in visited:
            visited.add(current_id)
            agent = self._agents.get(current_id)
            if agent is None:
                break
            chain.append(agent)
            current_id = agent.fallback_agent_id

        return chain

    def find_healthy_fallback(self, agent_id: str) -> AgentDefinition | None:
        chain = self.resolve_fallback_chain(agent_id)
        return next((a for a in chain if self.is_healthy(a.id) and a.id != agent_id), None)

    # ── 指标 ────────────────────────────────────────────────────────────

    def get_metrics(self, agent_id: str) -> AgentMetrics | None:
        return self._metrics.get(agent_id)

    def get_all_metrics(self) -> list[AgentMetrics]:
        return list(self._metrics.values())

    def reset_circuit_breaker(self, agent_id: str) -> None:
        breaker = self._breakers.get(agent_id)
        if breaker:
            breaker.reset()
        m = self._metrics.get(agent_id)
        if m:
            m.circuit_breaker_state = "CLOSED"

    # ── 内部 ────────────────────────────────────────────────────────────

    @staticmethod
    def _running_avg(prev: float, next_val: float, count: int) -> float:
        if count <= 1:
            return next_val
        return prev + (next_val - prev) / count

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, int(pct * len(sorted_vals)) - 1)
        return sorted_vals[idx]

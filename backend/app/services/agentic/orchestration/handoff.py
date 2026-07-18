"""Handoff 协议 —— 从 EstateWise handoff.ts 翻译。

Agent 间交接协议：深度限制、环路检测、健康检查、自动降级。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .types import (
    AgentError,
    AgentErrorType,
    HandoffPayload,
    HandoffType,
    TaskResult,
)
from .agent_registry import AgentRegistry

# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

MAX_HANDOFF_DEPTH = 3  # 最大交接链深度


@dataclass
class HandoffConfig:
    max_depth: int = MAX_HANDOFF_DEPTH
    max_iterations: int = 3
    enable_cycle_detection: bool = True
    timeout_per_agent_s: float = 30.0


@dataclass
class HandoffResult:
    success: bool
    payload: HandoffPayload
    result: TaskResult | None = None
    error: AgentError | None = None
    fallback_used: bool = False
    actual_agent_id: str = ""


class HandoffManager:
    """Agent 间交接管理器。

    参考 EstateWise HandoffManager：
    - 深度限制：最多 3 层交接
    - 环路检测：同一 Agent 不能在同一链中出现两次
    - 健康检查：不健康 → 自动找 fallback
    - 降级：全部失败 → SynthesizerAgent 兜底
    """

    def __init__(
        self,
        registry: AgentRegistry,
        config: HandoffConfig | None = None,
    ) -> None:
        self.registry = registry
        self.config = config or HandoffConfig()
        self._active_chains: dict[str, list[HandoffPayload]] = {}

    def can_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        call_chain: list[str],
    ) -> tuple[bool, str]:
        """检查是否允许交接。

        Returns:
            (allowed, reason) — reason 为空字符串表示允许。
        """
        # 深度限制
        if len(call_chain) >= self.config.max_depth:
            return False, f"交接链超过最大深度 {self.config.max_depth}"

        # 环路检测
        if self.config.enable_cycle_detection and to_agent_id in call_chain:
            chain_str = " → ".join(call_chain)
            return False, f"检测到环路: {chain_str} → {to_agent_id}"

        # 目标 Agent 健康检查
        if not self.registry.is_healthy(to_agent_id):
            fallback = self.registry.find_healthy_fallback(to_agent_id)
            if fallback is None:
                return False, f"目标 Agent {to_agent_id} 不健康且无可用降级"

        return True, ""

    async def handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        task_description: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, Any]],
        constraints: list[str] | None = None,
        handoff_type: HandoffType = HandoffType.DELEGATION,
        chain_id: str | None = None,
        execute_agent: Any = None,  # async callable: (agent_id, prompt) -> TaskResult
    ) -> HandoffResult:
        """执行一次 Agent 交接。

        Args:
            from_agent_id: 发起交接的 Agent
            to_agent_id: 目标 Agent
            task_description: 任务描述
            context: 上下文数据
            conversation_history: 对话历史
            constraints: 约束条件
            handoff_type: 交接类型
            chain_id: 链路 ID（None = 自动生成）
            execute_agent: async (agent_id, prompt) -> TaskResult

        Returns:
            HandoffResult
        """
        chain_id = chain_id or uuid.uuid4().hex[:12]
        chain = self._active_chains.get(chain_id, [])
        depth = len(chain)

        # ── 深度守卫 ──
        if depth >= self.config.max_depth:
            return HandoffResult(
                success=False,
                payload=self._build_payload(
                    from_agent_id, to_agent_id, task_description,
                    context, conversation_history, constraints or [],
                    handoff_type, chain_id, depth,
                ),
                error=AgentError(
                    type_=AgentErrorType.MAX_ITERATIONS_EXCEEDED,
                    message=f"交接链超过最大深度 {self.config.max_depth}",
                    agent_id=from_agent_id,
                    metadata={"chain_id": chain_id, "depth": depth},
                ),
                actual_agent_id=to_agent_id,
            )

        # ── 环路检测 ──
        visited = {p.from_agent_id for p in chain}
        visited.add(from_agent_id)
        if to_agent_id in visited:
            return HandoffResult(
                success=False,
                payload=self._build_payload(
                    from_agent_id, to_agent_id, task_description,
                    context, conversation_history, constraints or [],
                    handoff_type, chain_id, depth,
                ),
                error=AgentError(
                    type_=AgentErrorType.CIRCULAR_HANDOFF,
                    message=f'检测到环路交接: {" → ".join(visited)} → {to_agent_id}',
                    agent_id=from_agent_id,
                    metadata={"chain_id": chain_id, "visited": list(visited)},
                ),
                actual_agent_id=to_agent_id,
            )

        # ── 健康检查 + 自动降级 ──
        actual_target = to_agent_id
        fallback_used = False
        if not self.registry.is_healthy(to_agent_id):
            fallback = self.registry.find_healthy_fallback(to_agent_id)
            if fallback:
                actual_target = fallback.id
                fallback_used = True
            else:
                return HandoffResult(
                    success=False,
                    payload=self._build_payload(
                        from_agent_id, to_agent_id, task_description,
                        context, conversation_history, constraints or [],
                        handoff_type, chain_id, depth,
                    ),
                    error=AgentError(
                        type_=AgentErrorType.DEPENDENCY_FAILURE,
                        message=f"目标 Agent {to_agent_id} 不健康且无可用降级",
                        agent_id=from_agent_id,
                        metadata={"chain_id": chain_id},
                    ),
                    actual_agent_id=to_agent_id,
                )

        payload = self._build_payload(
            from_agent_id, actual_target, task_description,
            context, conversation_history, constraints or [],
            handoff_type, chain_id, depth,
        )

        # 追踪链路
        chain.append(payload)
        self._active_chains[chain_id] = chain

        # ── 执行目标 Agent ──
        if execute_agent is None:
            return HandoffResult(
                success=False,
                payload=payload,
                error=AgentError(
                    type_=AgentErrorType.DEPENDENCY_FAILURE,
                    message="未提供 execute_agent 回调",
                    agent_id=from_agent_id,
                ),
                fallback_used=fallback_used,
                actual_agent_id=actual_target,
            )

        prompt = self._build_handoff_prompt(payload)
        try:
            result = await execute_agent(actual_target, prompt)
            return HandoffResult(
                success=result.success,
                payload=payload,
                result=result,
                fallback_used=fallback_used,
                actual_agent_id=actual_target,
            )
        except Exception as exc:
            return HandoffResult(
                success=False,
                payload=payload,
                error=AgentError(
                    type_=AgentErrorType.EXTERNAL_API_FAILURE,
                    message=str(exc),
                    agent_id=actual_target,
                    cause=exc,
                ),
                fallback_used=fallback_used,
                actual_agent_id=actual_target,
            )

    # ── 内部 ────────────────────────────────────────────────────────────

    def _build_payload(
        self,
        from_agent_id: str,
        to_agent_id: str,
        task_description: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, Any]],
        constraints: list[str],
        handoff_type: HandoffType,
        chain_id: str,
        depth: int,
    ) -> HandoffPayload:
        import time
        return HandoffPayload(
            type=handoff_type,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            task_description=task_description,
            context=context,
            conversation_history=conversation_history,
            constraints=constraints,
            depth=depth,
            chain_id=chain_id,
            timestamp=time.time(),
        )

    def _build_handoff_prompt(self, payload: HandoffPayload) -> str:
        """构建给接收 Agent 的交接 prompt（XML 格式，与 EstateWise 一致）。"""
        recent = payload.conversation_history[-10:]
        history_xml = "\n".join(
            f'  <message role="{m.get("role", "user")}">{m.get("content", "")[:300]}</message>'
            for m in recent
        )

        constraints_xml = "\n".join(
            f"  <constraint>{c}</constraint>" for c in payload.constraints
        ) if payload.constraints else "  <constraint>none</constraint>"

        context_xml = "\n".join(
            f'  <entry key="{k}">{str(v)[:500]}</entry>'
            for k, v in payload.context.items()
        ) if payload.context else '  <entry key="none">empty</entry>'

        return f"""<handoff type="{payload.type.value}" depth="{payload.depth}">
  <from>{payload.from_agent_id}</from>
  <to>{payload.to_agent_id}</to>
  <task>{payload.task_description}</task>
  <context>
{context_xml}
  </context>
  <history>
{history_xml}
  </history>
  <constraints>
{constraints_xml}
  </constraints>
</handoff>"""

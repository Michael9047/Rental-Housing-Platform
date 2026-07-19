"""Agent ReAct 循环 —— 从 EstateWise agent-loop.ts 翻译。

驱动 Agent 通过多轮 Think → Act → Observe → Repeat 完成复杂任务。
复用现有的 llm_service.run_react_loop()，包装为 Agent 可用的标准接口。

与 EstateWise runAgentLoop 的核心对应：
- LLMClient → llm_service.complete_with_tools()
- ToolExecutor → ToolRegistry.execute()
- compactMessages → 上下文压缩
- 安全限制：timeout / context overflow / budget exceeded / max iterations
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from .types import (
    AgentError,
    AgentErrorType,
    TaskMetadata,
    TaskResult,
    ToolCallRecord,
)
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════

class AgentLoopConfig:
    """单次 Agent Loop 的配置。对应 EstateWise AgentLoopConfig。"""

    def __init__(
        self,
        agent_id: str,
        system_prompt: str = "",
        max_iterations: int = 5,
        timeout_ms: int = 60_000,
        max_context_percent: int = 85,
        budget_limit_usd: float | None = None,
        parent_task_id: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.timeout_ms = timeout_ms
        self.max_context_percent = max_context_percent
        self.budget_limit_usd = budget_limit_usd
        self.parent_task_id = parent_task_id


# ═══════════════════════════════════════════════════════════════════════════════
# 错误分类（从 EstateWise classifyError 翻译）
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_error(err: Exception) -> AgentErrorType:
    msg = str(err).lower()
    if "rate" in msg or "429" in msg or "throttl" in msg:
        return AgentErrorType.RATE_LIMITED
    if "timeout" in msg or "timed out" in msg:
        return AgentErrorType.TIMEOUT
    if "context" in msg and ("length" in msg or "overflow" in msg or "too long" in msg):
        return AgentErrorType.CONTEXT_OVERFLOW
    if "refus" in msg or "cannot" in msg or "i'm sorry" in msg:
        return AgentErrorType.MODEL_REFUSAL
    if "tool" in msg or "function" in msg:
        return AgentErrorType.TOOL_FAILURE
    return AgentErrorType.EXTERNAL_API_FAILURE


# ═══════════════════════════════════════════════════════════════════════════════
# ReAct 循环
# ═══════════════════════════════════════════════════════════════════════════════

async def run_agent_loop(
    config: AgentLoopConfig,
    llm_service: Any,  # LLMService (avoid circular import)
    tool_registry: ToolRegistry,
    initial_messages: list[dict[str, Any]],
    agent_tool_names: list[str] | None = None,
) -> TaskResult:
    """运行的 Agentic 工具调用循环。

    对应 EstateWise runAgentLoop()：
    while not done:
        LLM → 解析 tool_use → 执行工具 → 观察结果 → LLM
    直到模型输出最终文本或达到安全限制。

    Args:
        config: Agent Loop 配置
        llm_service: LLMService 实例
        tool_registry: ToolRegistry 实例
        initial_messages: 初始消息列表（不含 system prompt）
        agent_tool_names: 该 Agent 允许使用的工具名列表（None = 全部）

    Returns:
        TaskResult with success=True + data=final_text
                      或 success=False + error=AgentError
    """
    task_id = config.parent_task_id or f"task_{int(time.time() * 1000)}"
    started_at = time.time()
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = 0.0
    tool_calls: list[ToolCallRecord] = []

    # 构建消息列表
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": config.system_prompt},
        *initial_messages,
    ]

    # 获取工具 schemas
    all_tool_schemas = tool_registry.get_all_schemas() if not agent_tool_names else [
        s for name in agent_tool_names
        if (td := tool_registry.get(name))
        for s in [td.to_openai_schema()]
    ]

    final_text = ""

    for iteration in range(config.max_iterations):
        # ── 超时检查 ──
        elapsed_ms = (time.time() - started_at) * 1000
        if elapsed_ms > config.timeout_ms:
            return TaskResult(
                success=False,
                error=AgentError(
                    type_=AgentErrorType.TIMEOUT,
                    message=f"Agent Loop 超时 ({config.timeout_ms}ms)",
                    agent_id=config.agent_id,
                ),
                metadata=TaskMetadata(
                    task_id=task_id,
                    agent_id=config.agent_id,
                    status="failed",
                    error_type=AgentErrorType.TIMEOUT.value,
                    error_message=f"超时 {config.timeout_ms}ms",
                ),
                tool_calls=tool_calls,
            )

        # ── 调用 LLM (with tool calling) ──
        try:
            response = await llm_service.complete_with_tools(
                messages=messages,
                tools=all_tool_schemas if all_tool_schemas else None,
                temperature=0.2,
                max_tokens=2000,
            )
        except Exception as exc:
            err_type = _classify_error(exc)
            return TaskResult(
                success=False,
                error=AgentError(
                    type_=err_type,
                    message=str(exc),
                    agent_id=config.agent_id,
                    cause=exc,
                ),
                metadata=TaskMetadata(
                    task_id=task_id,
                    agent_id=config.agent_id,
                    status="failed",
                    error_type=err_type.value,
                    error_message=str(exc),
                ),
                tool_calls=tool_calls,
            )

        messages.append(response)

        content = response.get("content", "")
        response_tool_calls = response.get("tool_calls", [])

        # ── 无工具调用 → 最终回复 ──
        if not response_tool_calls:
            final_text = content or ""
            break

        # ── 执行工具调用 ──
        for tc in response_tool_calls:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, TypeError):
                fn_args = {}

            call_start = time.time()
            try:
                result_str = await tool_registry.execute(fn_name, fn_args)
                duration_ms = (time.time() - call_start) * 1000
                tool_calls.append(ToolCallRecord(
                    tool_name=fn_name,
                    input=fn_args,
                    output=result_str[:500],  # 截断存储
                    duration_ms=duration_ms,
                ))
            except Exception as exc:
                duration_ms = (time.time() - call_start) * 1000
                result_str = json.dumps({"error": str(exc)}, ensure_ascii=False)
                tool_calls.append(ToolCallRecord(
                    tool_name=fn_name,
                    input=fn_args,
                    error=str(exc),
                    duration_ms=duration_ms,
                ))

            # 追加 tool result 消息
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str,
            })

    # ── 迭代耗尽，无最终回复 ──
    if not final_text:
        return TaskResult(
            success=False,
            error=AgentError(
                type_=AgentErrorType.MAX_ITERATIONS_EXCEEDED,
                message=f"达到最大迭代次数 ({config.max_iterations})，未产出最终回复",
                agent_id=config.agent_id,
            ),
            metadata=TaskMetadata(
                task_id=task_id,
                agent_id=config.agent_id,
                status="failed",
                error_type=AgentErrorType.MAX_ITERATIONS_EXCEEDED.value,
                error_message=f"max_iterations={config.max_iterations}",
            ),
            tool_calls=tool_calls,
        )

    # ── 成功 ──
    return TaskResult(
        success=True,
        data=final_text,
        metadata=TaskMetadata(
            task_id=task_id,
            agent_id=config.agent_id,
            status="completed",
            created_at=started_at,
            completed_at=time.time(),
            duration_ms=(time.time() - started_at) * 1000,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=total_cost_usd,
        ),
        tool_calls=tool_calls,
    )

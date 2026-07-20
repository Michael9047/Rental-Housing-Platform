"""Agent 基类 —— 所有专业 Agent 的抽象基类。

参考 EstateWise 的 Agent 模型：
- 简单 Agent（Cart/FAQ）覆盖 handle()
- 复杂 Agent（Search/Compare）使用 handle_with_react()
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.agentic.orchestration.types import (
    AgentContext,
    AgentError,
    AgentErrorType,
    AgentResult,
    ToolCallRecord,
)
from app.services.agentic.orchestration.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent:
    """Agent 基类。

    name / description / tools 是每个 Agent 的元数据。
    AgentRegistry 根据这些元数据进行能力查找和路由。
    """

    name: str = "base"
    description: str = "Base agent"
    tools: list[str] = []  # 该 Agent 可用的 tool name 列表（在 ToolRegistry 中注册）

    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self._tool_registry = tool_registry or ToolRegistry.get_instance()
        self._llm_service = None

    @property
    def llm_service(self):
        if self._llm_service is None:
            from app.services.llm_service import get_llm_service
            self._llm_service = get_llm_service()
        return self._llm_service

    # ── 主入口 ────────────────────────────────────────────────────────

    async def handle(self, context: AgentContext) -> AgentResult:
        """默认：直接用 LLM 生成回复（无 ReAct）。

        简单 Agent（Cart/FAQ/Synthesizer）覆盖此方法。
        复杂 Agent（Search/Compare）覆盖 handle_with_react()。
        """
        raise NotImplementedError(f"{self.name}.handle() 未实现")

    async def handle_with_react(
        self,
        context: AgentContext,
        system_prompt: str | None = None,
        max_iterations: int = 3,
    ) -> AgentResult:
        """使用 ReAct loop 执行（Search/Compare/Market 等复杂 Agent）。

        Think → Act → Observe → Repeat → Reply
        """
        from app.services.agentic.orchestration.agent_loop import (
            AgentLoopConfig,
            run_agent_loop,
        )

        config = AgentLoopConfig(
            agent_id=self.name,
            system_prompt=system_prompt or self._default_system_prompt(),
            max_iterations=max_iterations,
        )

        initial_messages = [
            {"role": "user", "content": context.user_message},
        ]
        if context.history:
            for h in context.history[-6:]:
                initial_messages.append({
                    "role": h.get("role", "user"),
                    "content": str(h.get("content", ""))[:500],
                })

        result = await run_agent_loop(
            config=config,
            llm_service=self.llm_service,
            tool_registry=self._tool_registry,
            initial_messages=initial_messages,
            agent_tool_names=self.tools if self.tools else None,
        )

        if result.success and result.data:
            return AgentResult(
                content=str(result.data),
                success=True,
                tool_calls=result.tool_calls,
            )
        else:
            return AgentResult(
                content="",
                success=False,
                error=result.error,
                tool_calls=result.tool_calls,
            )

    # ── 工具执行器（ReAct loop 回调） ─────────────────────────────────

    async def _tool_executor(self, tool_name: str, args: dict[str, Any]) -> str:
        """ReAct loop 回调：执行指定工具并返回结果字符串。"""
        return await self._tool_registry.execute(tool_name, args)

    # ── 内部 ──────────────────────────────────────────────────────────

    def _default_system_prompt(self) -> str:
        return f"你是 {self.name}。完成分配给您的任务。"

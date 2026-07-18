"""Supervisor —— 从 EstateWise supervisor.ts 翻译。

核心编排器：分类 → 构建 DAG → 拓扑执行 → 合成回复。
替代 AgentService.handle_message() 的线性流水线。

支持三种执行路径：
- handle_message:      DAG 固定拓扑（expert 模式）
- handle_message_handoff: Agent 动态交接链（handoff 深度模式）
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .types import (
    AgentContext,
    AgentError,
    AgentErrorType,
    AgentResult,
    ExecutionMode,
    ExecutionPlan,
    ExecutionStep,
    HandoffType,
    TaskResult,
    TaskStatus,
)
from .agent_registry import AgentRegistry
from .tool_registry import ToolDef, ToolRegistry
from .execution_dag import ExecutionDAG
from .routing_strategy import RoutingStrategy, RoutingSignals
from .agent_loop import AgentLoopConfig, run_agent_loop
from .handoff import HandoffManager

logger = logging.getLogger(__name__)

# ── Handoff 链上下文（Agent 通过 tool 调用 handoff_to 时写入，Supervisor 读取） ──
_handoff_target: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "handoff_target", default=None
)
_handoff_task: contextvars.ContextVar[str] = contextvars.ContextVar(
    "handoff_task", default=""
)
_handoff_reason: contextvars.ContextVar[str] = contextvars.ContextVar(
    "handoff_reason", default=""
)

# 最大 Handoff 链深度
_MAX_HANDOFF_CHAIN_DEPTH = 5
# Handoff 链总超时（秒）
_HANDOFF_CHAIN_TIMEOUT_S = 60.0


# ═══════════════════════════════════════════════════════════════════════════════
# 意图分类（EstateWise 风格的关键词匹配 + 我们的 LLM 分类器）
# ═══════════════════════════════════════════════════════════════════════════════

# 中文找房关键词
_SEARCH_KEYWORDS = [
    "找", "推荐", "租", "房源", "房子", "居室", "单间", "公寓", "合租",
    "别墅", "预算", "地铁", "学校", "大学", "附近", "元", "块", "㎡", "平米",
    "想租", "看看", "有没有", "多少钱", "价格",
]

_COMPARE_KEYWORDS = ["对比", "比较", "哪个好", "哪套好", "vs", "pk", "帮我看看"]

_CART_KEYWORDS = ["加入", "购物车", "候选", "清单", "收藏", "移除", "删除", "加购"]

_FAQ_KEYWORDS = ["押金", "合同", "退款", "预订", "流程", "费用", "怎么看房", "签约"]

_MARKET_KEYWORDS = ["市场", "行情", "贵不贵", "均价", "价格怎么样", "趋势"]

_COMMUTE_KEYWORDS = ["通勤", "多远", "多久", "地铁站", "公交", "走路", "骑车", "开车"]

_POI_KEYWORDS = ["附近有", "周边", "超市", "餐馆", "健身房", "商场", "医院", "公园"]


class Supervisor:
    """中央编排器。

    参考 EstateWise Supervisor：
    handle_message() 是主入口，替代 AgentService.handle_message()。

    流程：
    1. 分类（RouterAgent 决策 fast/agentic）
    2. 构建 ExecutionDAG
    3. 拓扑排序 → 顺序/并行执行 Agent
    4. SynthesizerAgent 合成最终回复
    5. 持久化 SearchState
    """

    def __init__(
        self,
        session: AsyncSession,
        search_state: Any = None,
        registry: AgentRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.session = session
        self.search_state = search_state
        self.registry = registry or AgentRegistry()
        self.tool_registry = tool_registry or ToolRegistry.get_instance()
        self.routing = RoutingStrategy()
        self.handoff = HandoffManager(self.registry)
        self._llm_service = None

    @property
    def llm_service(self):
        if self._llm_service is None:
            from app.services.llm_service import get_llm_service
            self._llm_service = get_llm_service()
        return self._llm_service

    # ═══════════════════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════════════════

    async def handle_message(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        filters: dict[str, Any] | None = None,
        user_id: int | None = None,
        compare_property_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """主入口：处理用户消息，返回 Agent 回复。

        替代 AgentService.handle_message()。

        Returns:
            与 AgentService.handle_message() 兼容的 dict：
            {reply, intent, recommendations, cart_changed, ai_available, ...}
        """
        history = history or []
        start_time = time.time()

        # ── Step 1: 分类（意图 + 阶段 + 路由信号） ──
        classification = await self._classify(message, history)

        intent = classification.get("intent", "general")
        complexity = classification.get("complexity", 0.3)
        routing = classification.get("routing", "fast")

        # 前端候选清单显式触发对比（点击"对比所选"按钮）→ 强制对比意图
        if compare_property_ids and len(compare_property_ids) >= 2:
            intent = "compare"
            routing = "agent"

        # ── Step 2: 路由决策 ──
        signals = RoutingStrategy.from_classification(classification)
        signals.conversation_depth = len(history) // 2  # 粗略估算对话轮数
        route_decision = self.routing.evaluate(signals)

        # ── Step 3: 构建 DAG ──
        dag = ExecutionDAG.from_intent(
            intent=intent,
            complexity=complexity,
            enable_moe=(route_decision.mode == ExecutionMode.AGENTIC),
        )

        # ── Step 4: 执行 DAG ──
        context = AgentContext(
            user_message=message,
            history=history,
            filters=filters,
            user_id=user_id,
            search_state=self.search_state,
            extra={"compare_property_ids": compare_property_ids} if compare_property_ids else {},
        )

        agent_results: dict[str, AgentResult] = {}
        try:
            agent_results = await self._execute_dag(dag, context)
        except Exception as exc:
            logger.exception("DAG 执行失败")
            # 降级：使用 SynthesizerAgent 生成兜底回复
            fallback_result = await self._fallback_reply(message, str(exc))
            agent_results["synthesizer_agent"] = fallback_result

        # ── Step 5: 合成回复 ──
        final_reply = await self._synthesize(agent_results, classification)

        # ── Step 6: 构建响应（兼容现有 API 格式） ──
        return self._build_response(final_reply, classification, agent_results, start_time)

    # ═══════════════════════════════════════════════════════════════════════
    # Handoff 动态交接链（深度模式）
    # ═══════════════════════════════════════════════════════════════════════

    async def handle_message_handoff(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        filters: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """深度模式入口：Agent 动态交接链。

        Agent 之间可以动态决定将任务交接给谁，
        而非按照固定 DAG 执行。每个 Agent 的 ReAct loop 中
        可通过 handoff_to 工具将任务交给更合适的 Agent。

        流程：
        1. 分类 → 确定意图和初始路由
        2. RouterAgent 决策第一个 Agent
        3. 执行 Handoff 链：Agent → handoff_to → Agent → ... → Synthesizer
        4. 降级：超时/深度超限/全失败 → Synthesizer 兜底
        """
        history = history or []
        start_time = time.time()

        # ── Step 1: 分类 ──
        classification = await self._classify(message, history)
        intent = classification.get("intent", "general")

        # ── Step 2: 注册 handoff_to 工具 ──
        self._register_handoff_tool()

        # ── Step 3: 构建上下文 ──
        context = AgentContext(
            user_message=message,
            history=history,
            filters=filters,
            user_id=user_id,
            search_state=self.search_state,
        )

        # ── Step 4: 执行 Handoff 链 ──
        agent_results: dict[str, AgentResult] = {}
        handoff_chain: list[str] = []
        handoff_failed = False

        try:
            agent_results, handoff_chain = await self._run_handoff_chain(
                context=context,
                classification=classification,
            )
        except Exception as exc:
            logger.exception("Handoff 链执行失败")
            handoff_failed = True
            fallback_result = await self._fallback_reply(message, str(exc))
            agent_results["synthesizer_agent"] = fallback_result

        # ── Step 5: 合成回复 ──
        final_reply = await self._synthesize(agent_results, classification)

        # ── Step 6: 构建响应 ──
        response = self._build_response(final_reply, classification, agent_results, start_time)

        # 附加 Handoff 链信息
        response["_orchestration"]["mode"] = "handoff"
        response["_orchestration"]["handoff_chain"] = handoff_chain
        response["_orchestration"]["handoff_failed"] = handoff_failed

        return response

    def _register_handoff_tool(self) -> None:
        """注册 handoff_to 工具。

        当 Agent 的 ReAct loop 调用 handoff_to 时，
        将目标 Agent 和任务写入 contextvars，由 _run_handoff_chain 读取。
        """
        async def _handoff_to(
            target_agent: str,
            task_description: str,
            reason: str = "",
        ) -> dict[str, Any]:
            """将当前任务交接给另一个 Agent。

            Args:
                target_agent: 目标 Agent ID（如 commute_expert, search_agent 等）
                task_description: 交给目标 Agent 的任务描述
                reason: 为什么需要交接
            """
            # 验证目标 Agent 存在
            target_def = self.registry.get(target_agent)
            if target_def is None:
                return {
                    "success": False,
                    "error": f"未知 Agent: {target_agent}。可用 Agent: {[a.id for a in self.registry.list_all()[:10]]}...",
                }

            # 检查深度限制
            chain = _handoff_target.__class__.__dict__.get("_chain_depth", 0)
            if chain >= _MAX_HANDOFF_CHAIN_DEPTH:
                return {
                    "success": False,
                    "error": f"Handoff 链已达最大深度 {_MAX_HANDOFF_CHAIN_DEPTH}，请直接给出最终回复",
                }

            _handoff_target.set(target_agent)
            _handoff_task.set(task_description)
            _handoff_reason.set(reason)
            logger.info("Handoff: → %s (task=%s, reason=%s)", target_agent, task_description[:80], reason[:80])
            return {
                "success": True,
                "message": f"已将任务交接给 {target_agent}",
                "target": target_agent,
            }

        self.tool_registry.register(ToolDef(
            name="handoff_to",
            description="将当前任务交接给另一个专业 Agent。当你无法完成当前任务或需要其他 Agent 的专业能力时调用。调用后你的执行会暂停，目标 Agent 会接管任务。可用 Agent 列表请从系统提示中获取。",
            parameters={
                "type": "object",
                "properties": {
                    "target_agent": {
                        "type": "string",
                        "description": "目标 Agent 的 ID，如 search_agent, compare_agent, faq_agent, cart_agent 等",
                    },
                    "task_description": {
                        "type": "string",
                        "description": "交给目标 Agent 的具体任务描述",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么需要交接（用于日志追踪）",
                    },
                },
                "required": ["target_agent", "task_description"],
            },
            handler=_handoff_to,
            agent_names=[],  # 所有 Agent 都可用
        ))

    async def _run_handoff_chain(
        self,
        context: AgentContext,
        classification: dict[str, Any],
    ) -> tuple[dict[str, AgentResult], list[str]]:
        """执行 Agent 动态交接链。

        1. RouterAgent 决定起始 Agent
        2. 执行当前 Agent 的 ReAct loop
        3. 如果 Agent 调用了 handoff_to → 切换到目标 Agent
        4. 重复直到 Synthesizer 给出最终回复或达到限制

        Returns:
            (agent_results, handoff_chain) — agent_results 包含所有执行的 Agent 结果，
            handoff_chain 记录交接链路
        """
        agent_results: dict[str, AgentResult] = {}
        handoff_chain: list[str] = []
        start_time = time.time()

        # ── Step 1: RouterAgent 决策起始 Agent ──
        initial_agent = await self._run_router_for_handoff(context, classification)
        if initial_agent is None:
            # Router 失败 → 直接走 Synthesizer
            syn_result = await self._run_synthesizer(context, is_fallback=True)
            agent_results["synthesizer_agent"] = syn_result
            return agent_results, ["synthesizer_agent"]

        current_agent_id = initial_agent
        current_task = context.user_message
        logger.info("Handoff 链起始: %s", current_agent_id)

        # ── Step 2: 执行 Handoff 链 ──
        for depth in range(_MAX_HANDOFF_CHAIN_DEPTH):
            # 超时检查
            elapsed = time.time() - start_time
            if elapsed > _HANDOFF_CHAIN_TIMEOUT_S:
                logger.warning("Handoff 链超时 (%.1fs)", elapsed)
                syn_result = await self._run_synthesizer(context, is_fallback=True)
                agent_results["synthesizer_agent"] = syn_result
                handoff_chain.append("synthesizer_agent(fallback:timeout)")
                break

            # 清除上一次的 handoff 信号
            _handoff_target.set(None)
            _handoff_task.set("")
            _handoff_reason.set("")

            # 构建此 Agent 的上下文
            agent_context = AgentContext(
                user_message=current_task,
                history=context.history,
                filters=context.filters,
                user_id=context.user_id,
                search_state=context.search_state,
                extra={
                    **context.extra,
                    "handoff_chain": list(handoff_chain),
                    "handoff_depth": depth,
                },
            )

            # ── 执行当前 Agent ──
            agent_def = self.registry.get(current_agent_id)
            if agent_def is None:
                logger.warning("未知 Agent: %s，降级到 Synthesizer", current_agent_id)
                syn_result = await self._run_synthesizer(agent_context, is_fallback=True)
                agent_results["synthesizer_agent"] = syn_result
                handoff_chain.append("synthesizer_agent(fallback:unknown_agent)")
                break

            try:
                result = await self._run_react_agent(current_agent_id, agent_def, agent_context)
                agent_results[current_agent_id] = result
                handoff_chain.append(current_agent_id)
            except Exception as exc:
                logger.warning("Agent %s 执行失败: %s", current_agent_id, exc)
                agent_results[current_agent_id] = AgentResult(
                    content="", success=False,
                    error=AgentError(
                        type_=AgentErrorType.EXTERNAL_API_FAILURE,
                        message=str(exc), agent_id=current_agent_id,
                    ),
                )
                # 失败 → 降级到 Synthesizer
                syn_result = await self._run_synthesizer(agent_context, is_fallback=True)
                agent_results["synthesizer_agent"] = syn_result
                handoff_chain.append("synthesizer_agent(fallback:agent_error)")
                break

            # ── 检查是否有 handoff 请求 ──
            next_agent = _handoff_target.get()
            if next_agent:
                next_task = _handoff_task.get() or current_task
                reason = _handoff_reason.get()
                logger.info("Handoff #%d: %s → %s (%s)", depth + 1, current_agent_id, next_agent, reason)
                current_agent_id = next_agent
                current_task = next_task
                continue
            else:
                # 无 handoff → 当前 Agent 已给出最终回复
                # 运行 Synthesizer 做最后的整合
                syn_result = await self._run_synthesizer(context, is_fallback=False)
                agent_results["synthesizer_agent"] = syn_result
                handoff_chain.append("synthesizer_agent")
                break

        else:
            # 循环耗尽（达到最大深度）→ 强制 Synthesizer
            logger.warning("Handoff 链达到最大深度 %d，强制合成", _MAX_HANDOFF_CHAIN_DEPTH)
            syn_result = await self._run_synthesizer(context, is_fallback=True)
            agent_results["synthesizer_agent"] = syn_result
            handoff_chain.append("synthesizer_agent(fallback:max_depth)")

        logger.info("Handoff 链完成: %s", " → ".join(handoff_chain))
        return agent_results, handoff_chain

    async def _run_router_for_handoff(
        self,
        context: AgentContext,
        classification: dict[str, Any],
    ) -> str | None:
        """运行 RouterAgent 决定 Handoff 链的起始 Agent。

        如果 LLM 不可用，使用规则兜底选择起始 Agent。
        """
        intent = classification.get("intent", "general")
        sub_intent = classification.get("sub_intent", "")

        if not self.llm_service.is_available:
            # 规则兜底
            return self._rule_route_for_handoff(intent, sub_intent)

        # Build available agent catalog for router prompt
        all_agents = self.registry.list_all()
        catalog_lines = []
        for a in all_agents:
            if a.id != agent_name:
                catalog_lines.append(f"- {a.id}: {a.name} - {a.description}")
        agent_catalog = "\n".join(catalog_lines)

        router_prompt = f"""你是多 Agent 系统的智能路由器。根据用户消息和分类结果，决定第一个应该处理此请求的 Agent。

可用 Agent 列表：
{agent_catalog}

分类结果：
- intent: {intent}
- sub_intent: {sub_intent}
- stage: {classification.get("stage", "explore")}
- complexity: {classification.get("complexity", 0.3)}

路由规则：
- 找房/推荐 → filter_agent（有筛选条件时）或 search_agent（直接搜索）
- 对比房源 → compare_agent
- 通勤/周边/市场分析 → search_agent（search_agent 有 commute_calc/poi_lookup/market_stats 工具）
- FAQ/政策 → faq_agent
- 购物车操作 → cart_agent
- 无法判断 → search_agent

只输出目标 Agent ID，不要其他内容。"""

        try:
            result = await self.llm_service.complete_text(
                messages=[
                    {"role": "system", "content": router_prompt},
                    {"role": "user", "content": context.user_message},
                ],
                temperature=0.0,
                max_tokens=50,
            )
            agent_id = result.strip().lower()
            # 验证 Agent 存在
            if self.registry.get(agent_id):
                logger.info("RouterAgent 决策: %s", agent_id)
                return agent_id
            else:
                logger.warning("RouterAgent 返回未知 Agent: %s，使用规则兜底", agent_id)
                return self._rule_route_for_handoff(intent, sub_intent)
        except Exception:
            logger.debug("RouterAgent LLM 调用失败，使用规则兜底")
            return self._rule_route_for_handoff(intent, sub_intent)

    @staticmethod
    def _rule_route_for_handoff(intent: str, sub_intent: str) -> str:
        """规则兜底：根据意图选择起始 Agent。"""
        if intent == "search":
            return "filter_agent"
        elif intent == "compare":
            return "compare_agent"
        elif intent == "manage_cart":
            return "cart_agent"
        elif intent == "faq":
            return "faq_agent"
        else:
            return "search_agent"

    # ═══════════════════════════════════════════════════════════════════════
    # 分类
    # ═══════════════════════════════════════════════════════════════════════

    async def _classify(
        self, message: str, history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """意图分类：复用现有 AgentService.classify_message()。

        现有统一分类器已支持：intent + sub_intent + stage + complexity + routing。
        """
        try:
            from app.services.agent_service import AgentService
            agent_svc = AgentService(self.session)
            return await agent_svc.classify_message(message, history)
        except Exception:
            logger.debug("LLM 分类不可用，使用规则兜底")
            return self._rule_classify(message)

    def _rule_classify(self, message: str) -> dict[str, Any]:
        """规则兜底分类（LLM 不可用时）。"""
        text = message.strip()

        # 找房信号
        if any(kw in text for kw in _SEARCH_KEYWORDS):
            return {
                "intent": "search", "sub_intent": "browse",
                "stage": "explore", "complexity": 0.5,
                "confidence": 0.6, "routing": "agent",
            }
        # 对比信号
        if any(kw in text for kw in _COMPARE_KEYWORDS):
            return {
                "intent": "compare", "sub_intent": "cart",
                "stage": "compare", "complexity": 0.6,
                "confidence": 0.7, "routing": "agent",
            }
        # 购物车信号
        if any(kw in text for kw in _CART_KEYWORDS):
            return {
                "intent": "manage_cart", "sub_intent": "add",
                "stage": "explore", "complexity": 0.2,
                "confidence": 0.8, "routing": "fast",
            }
        # FAQ 信号
        if any(kw in text for kw in _FAQ_KEYWORDS):
            return {
                "intent": "faq", "sub_intent": "other",
                "stage": "general", "complexity": 0.1,
                "confidence": 0.7, "routing": "fast",
            }
        # 市场分析 → 统一走 search DAG（search_agent 有 market_stats 工具）
        if any(kw in text for kw in _MARKET_KEYWORDS):
            return {
                "intent": "search", "sub_intent": "market",
                "stage": "calibrate", "complexity": 0.5,
                "confidence": 0.6, "routing": "agent",
            }
        # 通勤 → 统一走 search DAG（search_agent 有 commute_calc 工具）
        if any(kw in text for kw in _COMMUTE_KEYWORDS):
            return {
                "intent": "search", "sub_intent": "commute",
                "stage": "narrow", "complexity": 0.4,
                "confidence": 0.6, "routing": "agent",
            }
        # POI → 统一走 search DAG（search_agent 有 poi_lookup 工具）
        if any(kw in text for kw in _POI_KEYWORDS):
            return {
                "intent": "search", "sub_intent": "poi",
                "stage": "narrow", "complexity": 0.4,
                "confidence": 0.6, "routing": "agent",
            }
        # 默认：闲聊
        return {
            "intent": "general", "sub_intent": "chitchat",
            "stage": "general", "complexity": 0.1,
            "confidence": 0.5, "routing": "fast",
        }

    # ═══════════════════════════════════════════════════════════════════════
    # DAG 执行
    # ═══════════════════════════════════════════════════════════════════════

    async def _execute_dag(
        self,
        dag: ExecutionDAG,
        context: AgentContext,
    ) -> dict[str, AgentResult]:
        """拓扑执行 DAG。同层节点可并行。

        参考 EstateWise Supervisor.executePlan()。
        """
        levels = dag.topological_sort()
        results: dict[str, AgentResult] = {}

        for level_idx, level in enumerate(levels):
            # 同层 Agent 并行执行
            if len(level) == 1:
                node = level[0]
                try:
                    result = await self._execute_agent(node.agent_name, context)
                    results[node.agent_name] = result

                except Exception as exc:
                    logger.warning("Agent %s 执行失败: %s", node.agent_name, exc)
                    results[node.agent_name] = AgentResult(
                        content="",
                        success=False,
                        error=AgentError(
                            type_=AgentErrorType.EXTERNAL_API_FAILURE,
                            message=str(exc),
                            agent_id=node.agent_name,
                        ),
                    )
            else:
                # 并行执行
                import asyncio
                async def _run_one(node):
                    try:
                        return node.agent_name, await self._execute_agent(node.agent_name, context)
                    except Exception as exc:
                        return node.agent_name, AgentResult(
                            content="", success=False,
                            error=AgentError(
                                type_=AgentErrorType.EXTERNAL_API_FAILURE,
                                message=str(exc), agent_id=node.agent_name,
                            ),
                        )

                tasks = [_run_one(node) for node in level]
                level_results = await asyncio.gather(*tasks, return_exceptions=True)
                for item in level_results:
                    if isinstance(item, tuple):
                        results[item[0]] = item[1]

        return results

    async def _execute_agent(
        self, agent_name: str, context: AgentContext
    ) -> AgentResult:
        """执行单个 Agent（精简后：全部直接执行，无 ReAct 开销）。

        - cart/faq/compare → 直接委托现有 Service 层
        - filter_agent → 单次 LLM JSON 提取（走 FilterAgent.handle()）
        - search_agent → 直接走 AgentService.recommend_properties() 成熟管线
        - synthesizer_agent → 单次 LLM 合成（走 SynthesizerAgent.handle()）
        """
        agent_def = self.registry.get(agent_name)

        # ── 购物车 Agent（无 LLM，直接委托现有 AgentService） ──
        if agent_name == "cart_agent":
            return await self._run_cart_agent(context)

        # ── FAQ Agent（无 LLM，规则匹配） ──
        if agent_name == "faq_agent":
            return await self._run_faq_agent(context)

        # ── 对比 Agent（复用现有 AgentService.compare_cart） ──
        if agent_name == "compare_agent":
            return await self._run_compare_agent(context)

        # ── 筛选 Agent（单次 LLM JSON 提取，走 filter_agent 自己的 FILTER_PROMPT） ──
        if agent_name == "filter_agent":
            return await self._run_filter_agent(context)

        # ── 搜索 Agent（直接走成熟旧管线，跳过 ReAct） ──
        if agent_name == "search_agent":
            return await self._run_search_agent(context)

        # ── 合成 Agent（单次 LLM 调用，按漏斗阶段适配语调） ──
        if agent_name == "synthesizer_agent":
            return await self._run_synthesizer_agent(context)

        # ── 降级：兜底回复 ──
        return await self._run_synthesizer(context, is_fallback=True)

    # ═══════════════════════════════════════════════════════════════════════
    # Agent 执行实现
    # ═══════════════════════════════════════════════════════════════════════

    async def _run_cart_agent(self, context: AgentContext) -> AgentResult:
        """购物车操作（委托现有 AgentService）。"""
        from app.services.agent_service import AgentService
        agent_svc = AgentService(self.session)
        try:
            # 直接使用现有的购物车方法
            cart, items = await agent_svc.get_cart_items(context.user_id or 0)
            props_text = "\n".join(
                f"{i+1}. [{it.property_id}] {it.property.title if it.property else '未知'}"
                for i, it in enumerate(items)
            ) if items else "购物车为空"
            return AgentResult(
                content=f"当前候选清单（共 {len(items)} 套）：\n{props_text}",
                success=True,
                data={"cart_id": cart.id, "items": [{"property_id": it.property_id} for it in items]},
            )
        except Exception as exc:
            return AgentResult(content="", success=False, error=AgentError(
                type_=AgentErrorType.TOOL_FAILURE, message=str(exc), agent_id="cart_agent",
            ))

    async def _run_faq_agent(self, context: AgentContext) -> AgentResult:
        """FAQ 规则匹配（委托现有 agent_faq）。"""
        from app.services.agent_faq import match_faq, get_faq
        message = context.user_message
        strength, hits = match_faq(message)

        if strength == "strong" and hits:
            entry = hits[0]
            return AgentResult(
                content=entry.answer,
                success=True,
                data={"faq_id": entry.id, "strength": "strong"},
            )
        elif strength == "weak" and hits:
            chips = [e.chip for e in hits[:5]]
            return AgentResult(
                content=f"你想了解的是 {' / '.join(chips)} 中的哪个？",
                success=True,
                data={"faq_id": None, "strength": "weak", "chips": chips},
            )
        else:
            # 尝试精确匹配
            entry = get_faq(message)
            if entry:
                return AgentResult(content=entry.answer, success=True, data={"faq_id": entry.id})
            return AgentResult(
                content="这是平台使用问题，建议查看帮助中心或联系客服。",
                success=True,
                data={"faq_id": None},
            )

    async def _run_compare_agent(self, context: AgentContext) -> AgentResult:
        """房源对比（委托现有 AgentService.compare_cart）。"""
        from app.services.agent_service import AgentService
        agent_svc = AgentService(self.session)
        try:
            result = await agent_svc.compare_cart(
                user_id=context.user_id or 0,
                priority="balanced",
            )
            return AgentResult(
                content=result.get("summary", ""),
                success=True,
                data=result,
            )
        except ValueError as exc:
            return AgentResult(
                content=str(exc),
                success=True,
                data={"error": str(exc)},
            )

    async def _run_search_agent(self, context: AgentContext) -> AgentResult:
        """房源搜索（复用现有 AgentService.recommend_properties，绕过 ReAct loop）。

        现有 recommend_properties 已经包含：
        extract_filters → search_with_relaxation → score → gap_detect → LLM 推荐回复。
        这是经过验证的成熟链路，直接复用比 ReAct 重新编排更可靠。
        """
        from app.services.agent_service import AgentService
        agent_svc = AgentService(self.session)
        try:
            result = await agent_svc.recommend_properties(
                message=context.user_message,
                filters=context.filters,
            )
            return AgentResult(
                content=result.get("reply", ""),
                success=True,
                data=result,
            )
        except Exception as exc:
            logger.exception("search_agent (recommend_properties) 失败")
            return AgentResult(
                content="",
                success=False,
                error=AgentError(
                    type_=AgentErrorType.EXTERNAL_API_FAILURE,
                    message=str(exc),
                    agent_id="search_agent",
                ),
            )

    async def _run_filter_agent(self, context: AgentContext) -> AgentResult:
        """筛选条件提取（单次 LLM JSON 提取，使用 filter_agent 的 FILTER_PROMPT）。

        FilterAgent.handle() 直接调用 llm_service.complete_json() 做单次 JSON 提取，
        含完整的设施口语映射表 + 硬约束/软偏好区分逻辑。不走 ReAct loop。
        """
        from app.services.agentic.agents.filter_agent import FilterAgent
        try:
            agent = FilterAgent()
            return await agent.handle(context)
        except Exception as exc:
            logger.exception("filter_agent 失败")
            return AgentResult(
                content="{}", success=True, data={},
                error=AgentError(
                    type_=AgentErrorType.TOOL_FAILURE,
                    message=str(exc), agent_id="filter_agent",
                ),
            )

    async def _run_synthesizer_agent(self, context: AgentContext) -> AgentResult:
        """回复合成（单次 LLM 调用，按漏斗阶段适配语调）。

        SynthesizerAgent.handle() 读取漏斗阶段并选择对应语气做单次 complete_text()，
        不走 ReAct loop。
        """
        from app.services.agentic.agents.synthesizer_agent import SynthesizerAgent
        try:
            agent = SynthesizerAgent()
            return await agent.handle(context)
        except Exception as exc:
            logger.warning("SynthesizerAgent LLM 失败: %s", exc)
            return AgentResult(
                content="抱歉，AI 服务暂时不可用。您可以尝试使用筛选功能来查找房源。",
                success=False,
            )

    async def _run_react_agent(
        self,
        agent_name: str,
        agent_def: Any,
        context: AgentContext,
    ) -> AgentResult:
        """使用 ReAct loop 执行 Agent（仅 Handoff 链使用，主 DAG 路径不再调用）。

        主 DAG 路径中，filter/search/synthesizer 均已改为直接执行：
        - filter → FilterAgent.handle()（单次 LLM JSON 提取）
        - search → AgentService.recommend_properties()（成熟管线）
        - synthesizer → SynthesizerAgent.handle()（单次 LLM 合成）
        """
        # 构建系统提示（含 Handoff 可用 Agent 列表）
        system_prompt = self._build_system_prompt(agent_name, context)

        config = AgentLoopConfig(
            agent_id=agent_name,
            system_prompt=system_prompt,
            max_iterations=2 if agent_name == "filter_agent" else 4,
            timeout_ms=agent_def.timeout_ms if agent_def else 60_000,
        )

        initial_messages = [
            {"role": "user", "content": context.user_message},
        ]
        if context.history:
            for h in context.history[-6:]:  # 最近 6 轮
                initial_messages.append({
                    "role": h.get("role", "user"),
                    "content": str(h.get("content", ""))[:500],
                })

        # 工具列表 = Agent 自有工具 + handoff_to（所有 Agent 都可用）
        agent_tools = list(agent_def.tools) if agent_def.tools else []
        if "handoff_to" not in agent_tools:
            agent_tools.append("handoff_to")

        result = await run_agent_loop(
            config=config,
            llm_service=self.llm_service,
            tool_registry=self.tool_registry,
            initial_messages=initial_messages,
            agent_tool_names=agent_tools,
        )

        if result.success and result.data:
            react_data: dict[str, Any] | None = None

            # search_agent: ReAct 生成文本回复，但前端需要结构化房源数据来渲染卡片
            if agent_name == "search_agent":
                try:
                    from app.services.agent_service import AgentService
                    agent_svc = AgentService(self.session)
                    structured = await agent_svc.recommend_properties(
                        message=context.user_message,
                        filters=context.filters,
                    )
                    react_data = {
                        "recommendations": structured.get("recommendations", []),
                        "top_picks": structured.get("top_picks", []),
                        "extracted_filters": structured.get("extracted_filters"),
                        "score_gap": structured.get("score_gap"),
                        "relaxation_level": structured.get("relaxation_level", 0),
                        "candidate_snapshot": structured.get("candidate_snapshot", []),
                        "source_info": structured.get("source_info", ""),
                        "needs_refinement": structured.get("needs_refinement", False),
                    }
                except Exception:
                    logger.exception("search_agent ReAct 后获取结构化数据失败")

            return AgentResult(
                content=str(result.data),
                success=True,
                tool_calls=result.tool_calls,
                data=react_data,
            )
        else:
            return AgentResult(
                content="",
                success=False,
                error=result.error,
                tool_calls=result.tool_calls,
            )

    async def _run_synthesizer(
        self, context: AgentContext, is_fallback: bool = False
    ) -> AgentResult:
        """兜底合成（LLM 不可用或全部 Agent 失败时使用）。"""
        if not self.llm_service.is_available:
            return AgentResult(
                content="我是西交利物浦大学周边的租房助手。请告诉我你想找的区域、预算和户型，我帮你筛房源。",
                success=True,
            )

        try:
            prompt = """你是西交利物浦大学周边的租房顾问。用 1-2 句话简洁回答用户的问题。
不要编造房源信息。如果用户输入不完整，礼貌引导补充关键信息（预算？区域？户型？通勤要求？）。"""

            reply = await self.llm_service.complete_text(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context.user_message},
                ],
                max_tokens=200,
            )
            return AgentResult(content=reply, success=True)
        except Exception:
            return AgentResult(
                content="抱歉，AI 服务暂时不可用。请稍后重试。",
                success=False,
            )

    async def _fallback_reply(self, message: str, error: str) -> AgentResult:
        """极端降级：所有 Agent 失败时用模板生成回复。"""
        from app.services.safe_fallback import build_fallback_response
        reply = build_fallback_response(
            query=message,
            active_filters={},
            relaxation_level=0,
        )
        return AgentResult(content=reply, success=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 合成
    # ═══════════════════════════════════════════════════════════════════════

    async def _synthesize(
        self,
        agent_results: dict[str, AgentResult],
        classification: dict[str, Any],
    ) -> str:
        """合成多个 Agent 的结果为最终回复。

        参考 EstateWise Supervisor.synthesizeResponse()。
        """
        successes: list[str] = []
        failures: list[str] = []

        for agent_name, result in agent_results.items():
            if result.success and result.content:
                successes.append(result.content)
            elif result.error:
                failures.append(f"[{agent_name}]: {result.error}")

        # 如果有成功的 Agent 输出，拼接
        if successes:
            return "\n\n".join(successes)

        # 全部失败 → 兜底
        if failures:
            return "抱歉，在处理您的请求时遇到了一些问题，请稍后重试。"

        return "我理解了您的需求，但暂时无法提供相关结果。请尝试换个方式描述。"

    # ═══════════════════════════════════════════════════════════════════════
    # 响应构建
    # ═══════════════════════════════════════════════════════════════════════

    def _build_response(
        self,
        reply: str,
        classification: dict[str, Any],
        agent_results: dict[str, AgentResult],
        start_time: float,
    ) -> dict[str, Any]:
        """构建与现有 AgentService.handle_message() 兼容的响应 dict。

        关键：对标 legacy AgentService.handle_message() 的 intent 映射规则：
        - search → recommend（前端据此渲染房源卡片）
        - faq / manage_cart / compare / general 保持原样
        """
        raw_intent = classification.get("intent", "general")
        # 映射到旧 intent 名，与 AgentService.handle_message() 保持一致
        intent_map = {
            "search": "recommend",
            "faq": "faq",
            "manage_cart": "manage_cart",
            "compare": "compare",
            "general": "general",
        }
        intent = intent_map.get(raw_intent, raw_intent)
        logger.info("SUPERVISOR _build_response: raw_intent=%s → intent=%s", raw_intent, intent)

        # 提取 search_agent 的完整结果（对标 recommend_properties 的返回格式）
        recommendations: list[dict] = []
        top_picks: list[dict] = []
        extracted_filters: dict | None = None
        score_gap: dict | None = None
        relaxation_level = 0
        candidate_snapshot: list[int] = []
        source_info = ""
        needs_refinement = False

        search_result = agent_results.get("search_agent")
        if search_result and search_result.success and search_result.data:
            data = search_result.data
            if isinstance(data, dict):
                recs = data.get("recommendations", [])
                if recs:
                    recommendations = recs
                top_picks = data.get("top_picks", [])
                extracted_filters = data.get("extracted_filters")
                score_gap = data.get("score_gap")
                relaxation_level = data.get("relaxation_level", 0)
                candidate_snapshot = data.get("candidate_snapshot", [])
                source_info = data.get("source_info", "")
                needs_refinement = data.get("needs_refinement", False)

        # 如果 search_agent 的回复内容非空，优先用它（而非合成后的拼接）
        quick_replies: list[str] = []
        if search_result and search_result.success and search_result.content:
            reply = search_result.content

        return {
            "reply": reply,
            "intent": intent,
            "recommendations": recommendations,
            "cart_changed": "cart_agent" in agent_results,
            "ai_available": self.llm_service.is_available,
            "quick_replies": quick_replies,
            "links": [],
            "extracted_filters": extracted_filters,
            "needs_refinement": needs_refinement,
            "top_picks": top_picks,
            "funnel_stage": classification.get("stage", "explore"),
            "score_gap": score_gap,
            "relaxation_level": relaxation_level,
            "candidate_snapshot": candidate_snapshot,
            "source_info": source_info,
            # 专家模式思考步骤（供前端展示 Agent 执行过程）
            "thinking_steps": _build_thinking_steps(agent_results),
            # 附加：编排元数据
            "_orchestration": {
                "mode": classification.get("routing", "fast"),
                "agents_executed": list(agent_results.keys()),
                "duration_ms": (time.time() - start_time) * 1000,
            },
        }

    # ═══════════════════════════════════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════════════════════════════════

    def _build_system_prompt(self, agent_name: str, context: AgentContext) -> str:
        """为 Agent 构建系统提示词（含漏斗阶段上下文 + Handoff 指令）。"""
        stage = ""
        if context.search_state:
            stage = getattr(context.search_state, "funnel_stage", "")
            stage = stage.value if hasattr(stage, "value") else str(stage)

        # 构建可用 Agent 列表（供 handoff_to 使用）
        all_agents = self.registry.list_all()
        agent_catalog_lines: list[str] = []
        for a in all_agents:
            if a.id != agent_name:
                agent_catalog_lines.append(f"  - {a.id}: {a.description}")
        agent_catalog = "\n".join(agent_catalog_lines[:20])  # 最多 20 个，避免 prompt 过长

        handoff_instructions = f"""
─── 交接能力 ───
你可以调用 handoff_to(target_agent, task_description, reason) 工具将任务交接给其他 Agent。
只有当你的专业能力无法满足当前需求时才使用交接，不要把简单任务也交接出去。
可用的 Agent：
{agent_catalog}
交接后你的执行会暂停，目标 Agent 会接管任务。
如果你能独立完成任务，直接输出中文回复即可，不要调用 handoff_to。"""

        prompts: dict[str, str] = {
            "search_agent": f"""你是租房搜索专家。当前漏斗阶段: {stage or "explore"}。

可用工具（按需使用，不要全部调用）：
- extract_filters: 从自然语言提取筛选条件（district/price_min/price_max/bedrooms/property_type/amenities）
- property_search: 搜索房源（支持 query + 结构化条件，自动渐进放宽）
- score_properties: 对搜索结果进行质量评分（传入 candidate_ids）
- gap_detect: 检测分数断层，判断是否果断推荐前N名
- safe_fallback_check: 检查检索质量是否足够
- query_rewrite: 改写模糊查询为精确条件（如"便宜一点"→降低预算）
- poi_lookup: 查询房源周边设施（超市/地铁/餐厅等）
- commute_calc: 计算房源通勤时间（需要房源坐标+目的地）

关键规则：
1. 先调用 extract_filters 从用户消息提取结构化条件
2. 调用 property_search 搜索（可同时传入 query 和 extract_filters 的结果）
3. 有结果 → 调用 score_properties 评分 → **立即用中文输出推荐回复**
4. 无结果 → 调用 safe_fallback_check → **立即用中文告知用户并给出放宽建议**
5. **最多调用 3 个工具**，之后必须输出中文文本回复
6. 回复格式：先总结匹配结果数量，再逐套介绍（价格/区域/户型/亮点）
7. 如果用户提到了通勤需求，可额外调用 commute_calc
8. 如果用户提到了周边配套需求，可额外调用 poi_lookup
{handoff_instructions}""",

            "filter_agent": f"""你是筛选条件提取专家。

你的任务：调用 extract_filters 工具从用户消息中提取结构化搜索条件。
调用一次工具后，**立即用中文输出提取到的条件摘要**，不要再调用其他工具。

输出格式示例：
"已提取条件：区域=苏州，最高预算=2000元，户型=单间"
{handoff_instructions}""",

            "synthesizer_agent": f"""你是租房对话回复合成专家。当前漏斗阶段: {stage or "explore"}。
将多个 Agent 的分析结果融合为自然、友好的中文回复。
- explore阶段：市场概览语气，引导用户细化需求
- calibrate阶段：比较性语气，帮用户理解价格与质量的对应关系
- narrow阶段：分析性语气，对比区域差异
- compare阶段：决策性语气，给出明确推荐
- decide阶段：行动导向，引导下一步（预约看房等）

如果需要检查检索质量，可以调用 safe_fallback_check 和 build_fallback_reply。
完成任务后必须直接输出中文文本回复。
{handoff_instructions}""",
        }

        return prompts.get(agent_name, f"你是 {agent_name}。完成分配给您的任务。{handoff_instructions}")


# ═══════════════════════════════════════════════════════════════════════════════
# 模块级辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _build_thinking_steps(agent_results: dict) -> list[dict]:
    """从 agent_results 中提取思考步骤，供前端展示 Agent 执行过程。

    每个步骤包含：agent_id, agent_name（中文）, status, summary, duration_ms
    """
    from .types import AgentResult

    # Agent 中文名映射
    _AGENT_CN_NAMES: dict[str, str] = {
        "filter_agent": "筛选条件提取",
        "search_agent": "房源搜索",
        "synthesizer_agent": "回复合成",
        "compare_agent": "房源对比",
        "cart_agent": "购物车管理",
        "faq_agent": "FAQ 问答",
    }

    steps = []
    for agent_id, result in agent_results.items():
        if not isinstance(result, AgentResult):
            continue

        status = "success" if result.success else "error"
        summary = ""
        duration_ms = 0

        # 提取摘要：优先用 data 里的 summary，否则截取 content 前 50 字
        if result.data and isinstance(result.data, dict):
            summary = result.data.get("summary", "")
            duration_ms = result.data.get("duration_ms", 0)
        if not summary and result.content:
            # 截取前 60 个字符作为摘要
            summary = result.content[:60] + ("..." if len(result.content) > 60 else "")
        if result.error:
            summary = f"错误: {str(result.error)[:80]}"

        steps.append({
            "agent_id": agent_id,
            "agent_name": _AGENT_CN_NAMES.get(agent_id, agent_id),
            "status": status,
            "summary": summary,
            "duration_ms": int(duration_ms or 0),
        })

    return steps

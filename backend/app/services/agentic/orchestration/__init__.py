"""编排引擎 —— 从 EstateWise 翻译的 Python 实现。

模块：
- types: 类型系统（AgentError, TaskResult, ExecutionPlan, ...）
- agent_registry: Agent 注册表 + 熔断器
- tool_registry: 工具注册表
- execution_dag: DAG 数据结构 + 拓扑排序
- routing_strategy: 5 信号加权路由决策
- agent_loop: ReAct 工具调用循环
- handoff: Agent 间交接协议
- supervisor: 中央编排器（替代 AgentService.handle_message()）
"""

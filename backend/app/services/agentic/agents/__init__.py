"""专业 Agent 集合。

任务 Agent：
- SearchAgent: 房源搜索 + 渐进放宽（EstateWise ReAct 模式，核心嫁接点）
- CompareAgent: 多维度对比（委托现有 AgentService.compare_cart）
- CartAgent: 购物车 CRUD（无 LLM）
- FAQAgent: FAQ 规则匹配（无 LLM）

分析 Agent：
- FilterAgent: NL → 结构化筛选
- MarketAgent: 价格分布、市场行情
- CommuteAgent: 通勤分析
- POIAgent: 周边设施
- ComplianceAgent: 合同/法规
- RankingAgent: 去重重排
- RelationAgent: 房源-POI 关系

MoE 专家组：
- PriceExpert / CommuteExpert / LifestyleExpert / SpaceExpert / AreaExpert
- MergerAgent: 加权投票融合

编排 + 合成：
- RouterAgent: 路由决策
- PlannerAgent: 任务分解
- ContextAgent: 上下文管理
- SynthesizerAgent: 多结果融合为自然语言
"""

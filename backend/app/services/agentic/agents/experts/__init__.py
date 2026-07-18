"""MoE（Mixture of Experts）专家组。

参考 EstateWise MoE Ensemble：5 个专家并行分析同一批房源，各从不同视角打分，
MergerAgent 加权融合。

专家：
- PriceExpert: 价格合理性（对应 EstateWise Data Analyst）
- CommuteExpert: 通勤便利性（对应 EstateWise Map Analyst）
- LifestyleExpert: 生活配套（对应 EstateWise Lifestyle Concierge）
- SpaceExpert: 户型效率（对应 EstateWise Data Analyst 的空间维度）
- AreaExpert: 区域安全/社区（对应 EstateWise Neighborhood Expert）
- MergerAgent: 加权投票融合（对应 EstateWise Master Merger）
"""

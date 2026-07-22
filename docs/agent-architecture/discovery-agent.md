# 发现 Agent — 详细设计

> 2026-07-13 | Michael

---

## 定位

帮助用户从模糊需求逐步收敛到 3-5 个候选房源。对话式、探索式交互。

---

## 意图路由总览

```mermaid
graph TD
    Start(["用户消息到达"]) --> LoadHistory["加载会话历史 (最近 10 条)"]
    LoadHistory --> ParseRefs["解析显式房源 ID (如 '房源 12')"]
    ParseRefs --> StageClassify["漏斗阶段分类<br/>LLM: explore / calibrate / narrow / compare / decide"]
    StageClassify --> FAQMatch["FAQ 规则匹配<br/>strong / weak / none"]
    FAQMatch --> HeuristicIntent["启发式意图识别<br/>(规则兜底)"]
    HeuristicIntent --> LLMIntent{"LLM 意图分类"}
    
    LLMIntent -->|"faq (strong)"| FAQDirect["直接 FAQ 回答<br/>+ 快捷选项 + 深度链接"]
    LLMIntent -->|"faq (weak)"| FAQConfirm["反问确认<br/>+ 选项按钮"]
    LLMIntent -->|"recommend"| Recommend["推荐管线<br/>⚠️ 核心流程"]
    LLMIntent -->|"add_to_cart"| AddCart["解析引用 → 加入 Cart"]
    LLMIntent -->|"remove_from_cart"| RemoveCart["解析引用 → 移除出 Cart"]
    LLMIntent -->|"compare_cart"| TriggerCompare["提示用户进入对比 Agent"]
    LLMIntent -->|"general"| GeneralChat["LLM 文本回复<br/>(最多 120 tokens)"]

    FAQDirect --> Persist
    FAQConfirm --> Persist
    Recommend --> Persist
    AddCart --> Persist
    RemoveCart --> Persist
    TriggerCompare --> Persist
    GeneralChat --> Persist

    Persist["持久化消息到 DB"] --> Return(["返回响应"])

    style Recommend fill:#4a90d9,color:#fff
    style TriggerCompare fill:#e8a838,color:#fff
```

---

## 推荐管线

这是发现 Agent 最复杂的路径。从用户自然语言到最终推荐结果：

```mermaid
graph TD
    R1(["用户说: 'UCL 附近 1200 以内 studio'"]) --> S1["Step 1: LLM 提取结构化筛选条件<br/>district · price_min/max · bedrooms · property_type"]
    S1 --> S2{"Step 2: 模糊度检查<br/>提取到 ≥ 2 个具体条件?"}
    
    S2 -->|"否"| Refine["返回 needs_refinement=True<br/>前端展示内联筛选卡片"]
    S2 -->|"是"| S3["Step 3: 合并筛选条件<br/>前端筛选器 > LLM 提取 > 历史状态"]
    
    S3 --> S4["Step 4: 搜索 + 渐进式放宽"]
    
    subgraph SearchLoop["搜索放宽循环"]
        R1_S["全文匹配搜索"] --> R1_C{"结果 ≥ 5?"}
        R1_C -->|"是"| R1_Out["输出"]
        R1_C -->|"否"| R2_S["放宽 1: 去掉户型限制"]
        R2_S --> R2_C{"结果 ≥ 5?"}
        R2_C -->|"是"| R1_Out
        R2_C -->|"否"| R3_S["放宽 2: 去掉卧室数限制"]
        R3_S --> R3_C{"结果 ≥ 5?"}
        R3_C -->|"是"| R1_Out
        R3_C -->|"否"| R4_S["放宽 3: price_max +20%"]
        R4_S --> R1_Out
    end

    S4 --> SearchLoop
    R1_Out --> S5["Step 5: 质量断层检测<br/>ScoreGap — 发现排名断崖"]
    S5 --> S6{"Step 6: 安全兜底?<br/>结果 = 0 或 top_score < 0.3"}
    S6 -->|"是"| Fallback["模板回复<br/>'没有完全匹配的房源...'"]
    S6 -->|"否"| S7["Step 7: 确定性质量评分<br/>价格匹配 40% + 空间匹配 20%<br/>+ 设施完整 20% + 基础分 20%"]
    S7 --> Top3["选出 Top 3 + 高亮理由"]
    Top3 --> S8["Step 8: LLM 生成推荐文案<br/>仅可引用 candidate_snapshot 内的 ID"]
    S8 --> S9["Step 9: 后验证<br/>_validate_recommendations()<br/>丢弃幻觉 ID"]
    S9 --> S10["Step 10: 更新 SearchState<br/>candidate_snapshot · filters · search_trail"]
    S10 --> Return(["返回: reply + recommendations + top_picks"])
    
    Fallback --> Return

    style S4 fill:#4a90d9,color:#fff
    style S7 fill:#4a90d9,color:#fff
    style S8 fill:#e8a838,color:#fff
```

---

## 漏斗阶段状态机

```mermaid
stateDiagram-v2
    [*] --> explore: 用户进入对话
    note right of explore: "我想在伦敦租房"<br/>模糊需求、浏览模式
    
    explore --> calibrate: 施加筛选条件
    note right of calibrate: "1200 以内，studio"<br/>调整预算/需求
    
    calibrate --> explore: 放宽条件
    calibrate --> narrow: 聚焦区域/户型
    note right of narrow: "Kings Cross 和 Camden<br/>哪个更适合学生?"<br/>区域间对比
    
    narrow --> calibrate: 调整条件
    narrow --> compare: 具体房源对比
    note right of compare: "房源 3 和房源 7<br/>帮我分析一下"<br/>关注具体房源
    
    compare --> narrow: 回到区域层面
    compare --> decide: 做出选择
    note right of decide: "就这套，约看房"<br/>进入决策阶段
    
    decide --> [*]: 跳转预约/对比 Agent
```

---

## 状态管理 (SearchState)

```mermaid
graph LR
    subgraph RedisState["Redis SearchState (TTL 2h)"]
        Stage["funnel_stage<br/>explore/calibrate/narrow/compare/decide"]
        Filters["active_filters<br/>{district, price, bedrooms...}"]
        Snapshot["candidate_snapshot<br/>[{property_id}...]"]
        Seen["seen_property_ids<br/>避免重复推荐"]
        Trail["search_trail<br/>每次搜索的条件+结果数"]
        Prefs["user_preferences<br/>{price_sensitivity...}"]
        Relax["last_relaxation_level<br/>0~3"]
        Gap["last_score_gap<br/>质量断层位置"]
    end

    UserMsg["用户消息"] --> Stage
    Filters --> Merge["合并筛选条件"]
    Snapshot --> Validate["LLM 幻觉校验"]
    Trail --> History["下次搜索参考"]
```

---

## 关键约束

| 规则 | 原因 |
|------|------|
| LLM 只能引用 `candidate_snapshot` 内的 ID | 防止幻觉房源 |
| 推荐结果后验证，丢弃无效 ID | 双重保险 |
| 每次 LLM 调用必须有确定性兜底 | LLM 不可用时系统仍可工作 |
| 模糊需求不追问，返回内联卡片 | 减少对话轮次，提升体验 |
| 优先使用前端筛选器，LLM 提取为辅 | 用户主动选择的意图最可靠 |

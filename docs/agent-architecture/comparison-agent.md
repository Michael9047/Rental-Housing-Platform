# 对比 Agent — 详细设计

> 2026-07-13 | Michael

---

## 定位

用户在备选清单中积累了 3-5 套房源后，进入深度对比。像买手机/买车一样，从多个维度系统性分析，辅助最终决策。

与发现 Agent 的本质区别：**不再探索新选项，只分析已有候选**。

---

## 整体流程

```mermaid
graph TD
    Start(["用户触发对比<br/>从 Cart 或对话中"]) --> LoadCart["从 AgentCart 读取备选清单"]
    LoadCart --> CountCheck{"房源数量?"}
    
    CountCheck -->|"< 2"| TooFew["提示: 至少需要 2 套房源<br/>引导用户继续收集"]
    CountCheck -->|"2~5"| FullCompare["全量深度对比"]
    CountCheck -->|"> 5"| AskNarrow["提示: 最多对比 5 套<br/>请先筛选"]
    
    TooFew --> Return1(["返回"])
    AskNarrow --> Return2(["返回"])
    
    FullCompare --> FetchData["拉取全量关联数据"]
    
    subgraph DataGathering["数据采集阶段"]
        FetchData --> PropData["房源基础数据<br/>价格 · 面积 · 户型 · 楼层 · 朝向 · 装修"]
        PropData --> CommuteData["通勤数据<br/>公交时间 · 骑车时间 · 步行距离"]
        CommuteData --> SafetyData["安全数据<br/>UK: Police.uk · SG: data.gov.sg"]
        SafetyData --> POIData["周边设施<br/>超市 · 餐厅 · 医院 · 药店"]
        POIData --> ReviewData["口碑数据<br/>评分 · 评价关键词 · 房东响应率"]
    end
    
    ReviewData --> Scoring["多维度确定性打分"]
    
    subgraph ScoringEngine["打分引擎"]
        S_Price["💰 总拥有成本<br/>月租 + 押金 + 水电网估算"]
        S_Commute["🚌 通勤<br/>公交优先 · 骑车/开车参考 · 步行加分"]
        S_Safety["🛡️ 安全<br/>犯罪率 vs 城市均值"]
        S_Space["📐 空间<br/>面积 · 独卫 · 储物"]
        S_Amenity["🏪 周边配套<br/>设施密度 · 距离"]
        S_Quality["🏠 房屋品质<br/>装修 · 朝向 · 楼层"]
        S_Landlord["👤 房东口碑<br/>评分 · 响应速度"]
    end
    
    Scoring --> LLMAnalysis["LLM 综合分析"]
    
    subgraph LLMRole["LLM 分析层 (只解释不打分)"]
        DimensionReport["逐维度分析<br/>每套房在各维度的优劣"]
        TradeOff["Trade-off 推理<br/>'A 贵 200 但通勤省 20 分钟'"]
        BestFor["Best For 推荐<br/>'追求性价比选 B，追求便利选 A'"]
        Caveats["风险提示<br/>'C 评分低但评价数少，需实地验证'"]
    end
    
    LLMAnalysis --> Output(["输出对比报告<br/>雷达图 · 维度表 · 分析文字 · 追问入口"])
```

---

## 对比维度详解

```mermaid
graph LR
    subgraph Hard["硬指标 (确定性打分)"]
        H1["💰 总拥有成本<br/>──────<br/>月租金<br/>押金 (几周?)<br/>中介费<br/>水电网估算<br/>管理费/物业费<br/>──────<br/>数据: Property"]
        H2["🚌 通勤<br/>──────<br/>公交: 时间+换乘<br/>骑车: 时间<br/>开车: 时间<br/>步行: ≤15min 加分<br/>──────<br/>数据: 路由 API"]
        H3["📐 空间<br/>──────<br/>总面积<br/>卧室数<br/>是否有独卫<br/>储物空间<br/>人均面积<br/>──────<br/>数据: Property"]
        H4["🏪 周边配套<br/>──────<br/>超市 (距离+数量)<br/>餐厅 (类型+评分)<br/>医院/诊所<br/>药店<br/>健身房<br/>──────<br/>数据: PropertyPOI"]
    end

    subgraph Soft["软指标 (数据辅助 + LLM 判断)"]
        S1["🛡️ 安全<br/>──────<br/>暴力犯罪率<br/>入室盗窃率<br/>vs 城市均值<br/>vs 对比组均值<br/>──────<br/>数据: Police.uk / data.gov.sg"]
        S2["🏠 房屋品质<br/>──────<br/>装修水平<br/>朝向/采光<br/>楼层<br/>隔音<br/>建筑年代<br/>──────<br/>数据: Property 描述 + Review"]
        S3["👤 房东口碑<br/>──────<br/>响应速度<br/>维修效率<br/>是否乱扣押金<br/>沟通语言<br/>──────<br/>数据: Review 聚合"]
    end

    Hard --> ScoringEngine["确定性打分引擎<br/>每维度 0-100"]
    Soft --> ScoringEngine
    ScoringEngine --> WeightedSum["用户权重加权<br/>balanced / budget / commute / safety / space"]
```

---

## 对比 Agent 对话流

```mermaid
sequenceDiagram
    actor User as 用户
    participant API as /api/v1/compare
    participant CA as ComparisonService
    participant Cart as AgentCart
    participant Property as PropertyService
    participant Safety as SafetyScoring
    participant POI as POIService
    participant LLM as LLMService
    participant DB as PostgreSQL

    User->>API: POST /compare/sessions<br/>{property_ids: [1,3,5,7]}
    API->>CA: start_comparison(user_id, property_ids)
    CA->>Cart: 读取 Cart 确认备选清单
    Cart-->>CA: [property_ids...]

    CA->>Property: 拉取房源全量数据
    Property->>DB: SELECT * + JOIN reviews + JOIN pois
    DB-->>Property: 完整数据
    Property-->>CA: PropertyMetrics[]

    par 并行拉取外部数据
        CA->>Safety: 评估每套房安全评分
        Safety->>Safety: Police.uk / data.gov.sg
        Safety-->>CA: safety_scores[]
    and
        CA->>POI: 周边设施聚合分析
        POI-->>CA: amenity_scores[]
    end

    CA->>CA: 多维度确定性打分 (0-100)
    CA->>CA: 按用户偏好权重计算加权总分

    CA->>LLM: COMPARISON_SYSTEM_PROMPT<br/>+ 结构化评分数据
    LLM-->>CA: 逐维度分析 + Trade-off + 推荐

    CA->>DB: 持久化对比 Session

    CA-->>API: CompareReport
    API-->>User: {<br/>  radar_chart_data,<br/>  dimension_table,<br/>  tradeoff_analysis,<br/>  best_for_recommendation,<br/>  property_details[],<br/>  session_id (用于追问)<br/>}

    Note over User,DB: 追问阶段

    User->>API: POST /compare/sessions/{id}/messages<br/>"A 的通勤比 B 好多少？"
    API->>CA: follow_up(session_id, message)
    CA->>LLM: 基于已有评分数据追问
    LLM-->>CA: 针对性分析
    CA-->>User: "A 公交 12 分钟直达校区，B 需换乘 1 次共 28 分钟..."
```

---

## 前端对比页面结构

```mermaid
graph TB
    subgraph ComparePage["对比页面布局"]
        direction TB

        subgraph Header["顶部操作栏"]
            PrioritySelector["偏好选择<br/>🏷️ 性价比优先 · 通勤优先 · 安全优先 · 面积优先"]
            ShareBtn["分享报告"]
            BookBtn["预约看房"]
        end

        subgraph MainContent["主内容区"]
            direction LR

            subgraph LeftCol["左侧: 可视化"]
                Radar["雷达图<br/>多维度叠加对比"]
                Ranking["综合排名<br/>1. A (82) · 2. B (76) · 3. C (71)"]
            end

            subgraph RightCol["右侧: 详细对比"]
                DimensionTable["维度对比表<br/>每行一个维度 · 每列一套房<br/>✅ ❌ ⚡ 图标标识"]
                TradeOffText["Trade-off 分析<br/>LLM 生成的自然语言<br/>'A 虽然贵 ¥200/月...'"]
                BestForCards["Best For 卡片<br/>🏆 性价比之王: B<br/>🚌 通勤最优: A<br/>🛡️ 最安全: C"]
            end
        end

        subgraph ChatPanel["底部: 追问区"]
            ChatInput["追问输入框<br/>'如果我只考虑通勤和安全呢?'"]
            ChatHistory["分析对话记录"]
        end
    end

    PrioritySelector --> Radar
    PrioritySelector --> DimensionTable
    Radar --> Ranking
    DimensionTable --> TradeOffText
    TradeOffText --> BestForCards
    ChatInput --> ChatHistory
```

---

## 与发现 Agent 的关键差异

| | 发现 Agent compare_cart (现有) | 对比 Agent (新建) |
|---|---|---|
| **维度数** | 4 (价格 · 通勤 · 空间 · 评分) | 7+ (价格 · 通勤 · 空间 · 配套 · 安全 · 品质 · 口碑) |
| **安全数据** | 无 | Police.uk + data.gov.sg |
| **通勤粒度** | 最近地铁站距离 | 公交路线时间 + 换乘次数 + 多种交通方式 |
| **评分模型** | 简单线性加权 | 加入上下文归一化 + 城市基准对比 |
| **LLM 深度** | 解释已有分数 | Trade-off 推理 + 风险提示 + 建议验证项 |
| **交互模式** | el-dialog 弹窗 | 独立页面 + 追问对话 |
| **输出** | 评分表 | 雷达图 + 维度表 + 分析报告 + 追问入口 |
| **持久化** | 无 (即抛) | 对比 Session 持久化，可回溯 |

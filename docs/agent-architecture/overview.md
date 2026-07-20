# 租房 Agent 系统整体架构

> 2026-07-13 | Michael

---

## 系统全景图

```mermaid
graph TB
    subgraph Frontend["前端 (Vue 3)"]
        AgentView["AgentView<br/>发现 Agent 对话页"]
        CompareView["CompareView<br/>对比 Agent 分析页"]
        FavoritesView["Favorites<br/>收藏页"]
        SearchView["Search<br/>手动检索页"]
    end

    subgraph API["API 层 (FastAPI)"]
        AgentRoutes["/api/v1/agent/*<br/>发现 Agent 路由"]
        CompareRoutes["/api/v1/compare/*<br/>对比 Agent 路由 (新)"]
        FavoriteRoutes["/api/v1/favorites/*"]
        SearchRoutes["/api/v1/properties/*"]
    end

    subgraph Agents["Agent 层"]
        DiscoveryAgent["🔍 发现 Agent<br/>DiscoveryService<br/>意图路由 · 漏斗管理 · 推荐 · FAQ"]
        ComparisonAgent["⚖️ 对比 Agent<br/>ComparisonService (新)<br/>多维分析 · Trade-off · 报告"]
    end

    subgraph Shared["共享服务层"]
        LLM["LLMService<br/>DeepSeek / OpenAI"]
        Property["PropertyService<br/>搜索 · pgvector · 关键词"]
        Cart["AgentCart<br/>备选清单 · 两 Agent 桥梁"]
        Embedding["EmbeddingService<br/>向量化"]
        POI["POIService<br/>周边设施"]
        Safety["SafetyScoring<br/>安全评分 (新)"]
        CompareEngine["CompareScoring<br/>打分引擎"]
        SearchState["SearchState<br/>Redis 会话状态"]
    end

    subgraph Data["数据层"]
        PG[("PostgreSQL<br/>+ pgvector")]
        Redis[("Redis<br/>SearchState · 缓存")]
    end

    subgraph External["外部数据源"]
        PoliceUK["Police.uk API<br/>英国犯罪数据"]
        DataGovSG["data.gov.sg<br/>新加坡犯罪数据"]
    end

    AgentView --> AgentRoutes --> DiscoveryAgent
    SearchView --> SearchRoutes
    CompareView --> CompareRoutes --> ComparisonAgent
    FavoritesView --> FavoriteRoutes

    DiscoveryAgent --> LLM
    DiscoveryAgent --> Property
    DiscoveryAgent --> Cart
    DiscoveryAgent --> Embedding
    DiscoveryAgent --> POI
    DiscoveryAgent --> CompareEngine
    DiscoveryAgent --> SearchState

    ComparisonAgent --> LLM
    ComparisonAgent --> Property
    ComparisonAgent --> Cart
    ComparisonAgent --> CompareEngine
    ComparisonAgent --> Safety
    ComparisonAgent --> POI

    Safety --> PoliceUK
    Safety --> DataGovSG

    Property --> PG
    Cart --> PG
    SearchState --> Redis
    Property --> Redis
```

---

## 设计原则

### 双 Agent 架构

| | 发现 Agent | 对比 Agent |
|---|---|---|
| **定位** | 帮你找到候选 | 帮你从候选中决策 |
| **交互模式** | 对话式、探索式 | 分析式、决策式 |
| **数据需求** | 广度 — 搜索结果快照 | 深度 — 拉取全量关联数据 |
| **LLM 角色** | 理解意图、引导提问、推荐排序 | 多维度分析、Trade-off 推理、自然语言解释 |
| **状态管理** | 漏斗阶段 + 搜索状态 (Redis) | 对比 Session + 用户权重偏好 |
| **输入** | 用户自然语言 + 筛选器 | Cart 中的 3-5 个房源 ID |
| **输出** | 推荐卡片 + 回复文字 | 雷达图 + 维度对比表 + Trade-off 分析 + 报告 |

### 为什么分开

1. **Single Responsibility** — 发现和决策是两个不同的用户心智模式，放在一个 Agent 里会导致 Prompt 臃肿、意图路由复杂
2. **独立演进** — 对比 Agent 以后加雷达图、分享报告、what-if 分析等功能，不会影响发现 Agent
3. **数据深度不同** — 发现只需快照级别数据，对比需要拉全量（安全、通勤详情、周边、房东口碑等）
4. **可测试性** — 各自独立可单独评估，不互相干扰

### Cart 是桥梁

```
发现 Agent ──写入──→ Cart ──读取──→ 对比 Agent
                  ↑
         手动检索页 ──写入──┘
```

两个 Agent 通过共享的 AgentCart 通信，彼此不直接依赖。

---

## 用户完整旅程

```mermaid
sequenceDiagram
    actor User as 用户
    participant DA as 发现 Agent
    participant Cart as AgentCart
    participant Search as 检索页
    participant CA as 对比 Agent

    Note over User,CA: 阶段 1 — 探索与发现

    User->>DA: "UCL 附近，月租 1200 以内"
    DA->>DA: 解析意图 → 提取筛选条件
    DA->>DA: 搜索 → 质量评分 → LLM 推荐
    DA-->>User: 推荐 3 套房 + 市场行情

    User->>DA: "通勤要 30 分钟以内"
    DA->>DA: 漏斗状态更新 → 重新搜索
    DA-->>User: 筛选后推荐 2 套

    User->>DA: "第二套加入备选"
    DA->>Cart: add_to_cart(property_id=42)
    DA-->>User: "已加入备选清单 ✓"

    Note over User,CA: 阶段 2 — 多渠道收集

    User->>Search: 手动检索 "伦敦一区 studio"
    Search-->>User: 搜索结果列表
    User->>Cart: 勾选收藏 → 加入备选

    User->>DA: "还有没有更便宜的？"
    DA-->>User: 推荐新结果
    User->>Cart: 加入备选

    Note over User,CA: 阶段 3 — 深度对比

    User->>CA: "开始对比我的备选清单" (5 套)
    CA->>Cart: 读取备选房源
    CA->>CA: 拉取全量数据 (安全 · 通勤 · 周边 · 品质)
    CA->>CA: 多维度打分
    CA->>CA: LLM Trade-off 分析
    CA-->>User: 雷达图 + 维度对比表 + 分析报告

    User->>CA: "帮我排除 C 和 E，重比 A B D"
    CA->>CA: 重新聚焦 3 套
    CA-->>User: 更新后的对比结果

    User->>CA: "A 的通勤比 B 好多少？"
    CA-->>User: "A 公交 12 分钟直达，B 需换乘共 28 分钟..."

    User->>CA: "就 A 了，帮我约看房"
    CA-->>User: 跳转预约页面
```

---

## 目录

```
docs/agent-architecture/
├── overview.md             # 本文件 — 整体架构
├── discovery-agent.md      # 发现 Agent 详细设计
├── comparison-agent.md     # 对比 Agent 详细设计
├── data-flow.md            # 数据流 & Cart 桥梁机制
└── safety-scoring.md       # 安全评分子系统
```

# 数据流 & Cart 桥梁机制

> 2026-07-13 | Michael

---

## Cart: 两个 Agent 的桥梁

```mermaid
graph TB
    subgraph Sources["备选清单来源"]
        DA_Cart["🤖 发现 Agent 对话中<br/>用户说 '加入备选'"]
        Search_Cart["🔍 手动检索页<br/>勾选房源 → 加入备选"]
        Fav_Cart["⭐ 收藏夹<br/>一键转入备选"]
    end

    subgraph CartDB["AgentCart (PostgreSQL)"]
        Cart["agent_carts<br/>user_id · session_id"]
        CartItems["agent_cart_items<br/>cart_id · property_id · added_reason · added_at"]
    end

    subgraph Consumers["备选清单消费者"]
        CA_Read["⚖️ 对比 Agent<br/>读取 → 深度对比"]
        DA_Read["🤖 发现 Agent<br/>读取 → 展示清单状态"]
        CompareView["📊 对比页面<br/>展示备选列表"]
    end

    DA_Cart -->|"POST /agent/sessions/{id}/messages<br/>{message: '加入备选'}"| Cart
    Search_Cart -->|"POST /agent/cart/items"| Cart
    Fav_Cart -->|"POST /agent/cart/items"| Cart

    Cart --> CartItems

    CartItems --> CA_Read
    CartItems --> DA_Read
    CartItems --> CompareView

    style Cart fill:#e8a838,color:#fff
    style CartItems fill:#e8a838,color:#fff
```

---

## 双渠道入篮流程

```mermaid
sequenceDiagram
    actor User as 用户
    participant AgentChat as 发现 Agent 对话
    participant SearchPage as 手动检索页
    participant CartAPI as Cart API
    participant CartDB as Cart DB
    participant AgentReply as Agent 回复

    Note over User,AgentReply: 渠道 A — Agent 对话中入篮

    User->>AgentChat: "第二套和第三套加入备选"
    AgentChat->>AgentChat: 意图识别 → add_to_cart
    AgentChat->>AgentChat: 解析引用: property_id=42, 57
    AgentChat->>CartAPI: add_to_cart(user_id, 42, "agent_recommend")
    CartAPI->>CartDB: UPSERT (去重)
    AgentChat->>CartAPI: add_to_cart(user_id, 57, "agent_recommend")
    AgentChat->>AgentReply: "已将 2 套加入备选清单 ✅<br/>当前共 3 套 | 去对比 →"

    Note over User,AgentReply: 渠道 B — 检索页入篮

    User->>SearchPage: 搜索 "伦敦一区 studio"
    SearchPage-->>User: 20 条结果
    User->>SearchPage: 勾选 3 套 → 点 "加入备选"
    SearchPage->>CartAPI: batch_add_to_cart(user_id, [12,18,31], "manual_search")
    CartAPI->>CartDB: 批量 UPSERT
    SearchPage-->>User: "已加入备选 ✅"

    Note over User,AgentReply: 汇合

    User->>AgentChat: "查看我的备选清单"
    AgentChat->>CartAPI: get_cart(user_id)
    CartAPI->>CartDB: SELECT cart_items + JOIN properties
    CartDB-->>CartAPI: 6 套 (3 agent + 3 search)
    AgentChat->>AgentReply: 展示清单 + "选 3-5 套开始深度对比"
```

---

## Cart 数据模型

```mermaid
erDiagram
    AgentCart {
        int id PK
        int user_id FK "唯一，一个用户一个 Cart"
        int latest_session_id FK "关联最近对话 session"
        datetime created_at
        datetime updated_at
    }

    AgentCartItem {
        int id PK
        int cart_id FK
        int property_id FK
        string added_reason "agent_recommend | manual_search | favorites"
        datetime added_at
    }

    Property {
        int id PK
        string title
        decimal price
        float area
        int bedrooms
        string district
        json description
    }

    AgentCart ||--o{ AgentCartItem : contains
    AgentCartItem }o--|| Property : references
```

UNIQUE constraint: `(cart_id, property_id)` — 同一房源不会重复入篮。

---

## 对比 Agent 的数据拉取

```mermaid
graph TD
    Start(["对比 Agent 启动"]) --> ReadCart["从 Cart 读取 property_ids"]
    ReadCart --> Parallel["并行数据拉取"]

    subgraph ParallelFetch["并行数据采集"]
        P1["PropertyService<br/>基础信息 + 描述"]
        P2["POIService<br/>周边设施聚合"]
        P3["SafetyScoring<br/>UK: Police.uk · SG: data.gov.sg"]
        P4["ReviewAggregation<br/>评分 · 关键词 · 房东响应率"]
        P5["RouteAPI<br/>公交路线时间 (外部 API)"]
    end

    Parallel --> ParallelFetch
    ParallelFetch --> Assemble["组装 PropertyMetrics[]"]

    subgraph PropertyMetrics["PropertyMetrics 数据结构"]
        direction TB
        PM1["property_id"]
        PM2["price_breakdown<br/>{rent, deposit, agency_fee, utilities_est}"]
        PM3["commute<br/>{bus_time, bus_transfers, cycle_time, walk_time}"]
        PM4["safety<br/>{overall_score, violent_rate, burglary_rate, vs_city_avg}"]
        PM5["space<br/>{area, bedrooms, en_suite, storage, per_person_area}"]
        PM6["amenities<br/>{supermarket_count, restaurant_variety, hospital_distance...}"]
        PM7["quality<br/>{furnishing, orientation, floor, age_band}"]
        PM8["landlord<br/>{rating, response_speed, keywords}"]
    end

    Assemble --> Scoring["进入打分引擎"]
```

---

## 对比 Session 的生命周期

```mermaid
sequenceDiagram
    participant User
    participant CA as 对比 Agent
    participant CS as CompareSession (DB)
    participant Cart as AgentCart

    User->>CA: 开始对比 (触发)
    CA->>Cart: 读取备选清单
    CA->>CS: 创建 CompareSession<br/>{user_id, property_ids[], status=active}

    loop 追问阶段 (可多轮)
        User->>CA: 追问 ("A 的通勤比 B 好多少")
        CA->>CS: 追加消息到 session
        CS-->>CA: 已有评分数据 (不重新拉取)
        CA->>CA: LLM 基于缓存数据回复
        CA-->>User: 回答
    end

    User->>CA: 结束对比 / 预约看房
    CA->>CS: status = completed<br/>保存最终报告快照
    CS-->>CA: session_id (可回溯)
    CA-->>User: 跳转预约 / 分享报告

    Note over CS: CompareSession 持久化<br/>用户可在历史记录中回溯<br/>不依赖 Redis (不像 SearchState)
```

---

## 与前端的通信协议

### 对比请求

```json
POST /api/v1/compare/sessions
{
  "property_ids": [12, 42, 57]
}
```

### 对比响应

```json
{
  "session_id": "cs_abc123",
  "radar_chart": {
    "dimensions": ["总成本", "通勤", "安全", "空间", "配套", "品质", "口碑"],
    "series": [
      {"property_id": 12, "title": "A 公寓", "scores": [82, 88, 75, 70, 90, 65, 72]},
      {"property_id": 42, "title": "B 公寓", "scores": [70, 62, 90, 85, 72, 80, 68]},
      ...
    ]
  },
  "dimension_table": [
    {
      "dimension": "通勤",
      "rows": [
        {"property_id": 12, "value": "公交 12 分", "icon": "✅", "detail": "直达，步行 3 分到站"},
        {"property_id": 42, "value": "公交 28 分", "icon": "⚠️", "detail": "需换乘 1 次"},
      ]
    },
    ...
  ],
  "tradeoff_analysis": "A 公寓虽然月租贵 ¥200，但通勤每天省 32 分钟...",
  "best_for": [
    {"label": "🏆 综合最佳", "property_id": 12},
    {"label": "💰 性价比之王", "property_id": 42},
    {"label": "🛡️ 最安全", "property_id": 57}
  ],
  "ranking": [12, 42, 57]
}
```

### 追问

```json
POST /api/v1/compare/sessions/cs_abc123/messages
{
  "message": "如果我只考虑通勤和安全呢？"
}

→
{
  "reply": "如果只看通勤和安全两个维度...",
  "updated_ranking": [57, 12, 42],
  "updated_radar_chart": { ... }
}
```

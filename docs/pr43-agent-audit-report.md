# PR #43 Agent 度化板块审计报告

> 审计日期：2026-08-05
> PR 分支：`feat/agent-streaming-property-compare`
> 对比基线：`main` (当前 HEAD: `9bc1f48`)
> PR 规模：89 文件，+16,840 / -1,535 行，7 个 commits

---

## 目录

1. [总体结论](#1-总体结论)
2. [核心搜索算法变更](#2-核心搜索算法变更)
3. [记忆机制](#3-记忆机制)
4. [缓存机制](#4-缓存机制)
5. [侧边栏与搜索结果协同](#5-侧边栏与搜索结果协同)
6. [侧边栏嫁接可行性分析](#6-侧边栏嫁接可行性分析)
7. [文件级合并清单](#7-文件级合并清单)

---

## 1. 总体结论

PR #43 是一次**底层架构级重写**，不是增量修补。核心从"LLM 驱动的多轮 ReAct 搜索"迁移到了"**确定性管线 + LLM 仅做回复生成**"。同时新增了完整的会话记忆、长期偏好和搜索审计体系。

```
旧架构：用户消息 → LLM 提取条件 → ReAct 串行工具调用(5-10轮, 30-90s) → LLM 生成回复 → 假流式(逐3字打印)
新架构：用户消息 → 确定性管线(0.3s预加载) → 7信号评分 → 单次LLM生成(10s) → 真SSE流式
```

---

## 2. 核心搜索算法变更

### 2.1 变更结论：**从根本上重写，不再是 ReAct，而是确定性管线**

### 2.2 逐维度对比

| 维度 | 之前 (main) | 之后 (PR #43) |
|------|------------|---------------|
| 搜索范式 | LLM ReAct Tool Loop（串行 5-10 次往返） | **确定性管线**：批量预加载 → 确定性评分 → 单次 LLM |
| 向量检索 | 拉取最多 500 条向量到应用层，NumPy 逐条计算 cosine | **pgvector HNSW 索引推至 DB 层**，`cosine_distance` 下推 SQL |
| 查询理解 | LLM 在 `search()` 内部 inline 提取筛选条件 | **独立模块 `query_understanding.py`**：确定性正则 → LLM 增强(温度=0)，正则结果覆盖 LLM |
| 召回策略 | 单一 `search_unit_types()` 调用 | **双路混合召回**（语义向量 + 结构化条件），合并去重 |
| 排序 | 原始 embedding 相似度 + 基础 `score_gap` | **7 信号确定性加权重排** |
| 零结果处理 | 无 | **约束消融**：逐项放宽，选择最小代价恢复结果 |
| 回复生成 | LLM 自由发挥，无事实约束 | **Grounded Answer**：只能引用 `candidates.facts`，缺失标注"暂无数据" |
| 流式输出 | 生成完毕后每 3 字假装打字（假流式） | **LLM token 真流式 SSE** |
| ReAct | 主路径（根据关键词自动切换） | **显式兼容 facade**，不再自动触发 |

### 2.3 7 信号重排权重

| 信号 | 权重 | 说明 |
|------|-----:|------|
| 语义相似度 | 32% | pgvector cosine distance |
| 词面匹配 | 12% | 中文 bigram + 英文词 token 覆盖 |
| 预算贴合 | 18% | 距预算目标的距离，偏好在 90% 预算处 |
| 通勤表现 | 14% | 通勤分钟数 vs 目标 |
| 周边 POI | 10% | 聚合 POI 距离归一化 |
| 信息完整度 | 8% | 7 项数据字段完整度检查 |
| 约束满足度 | 6% | 硬约束全过=1.0，放宽后=0.65 |

### 2.4 涉及的核心文件

| 文件 | 状态 | 行数 | 角色 |
|------|------|------|------|
| `backend/app/services/agentic/agents/search_agent.py` | 重写 | +728 / -302 | 搜索主逻辑：从 ReAct 改为管线执行器 |
| `backend/app/services/agentic/retrieval.py` | **新增** | 456 | 混合召回 + 约束消融 + 7 信号重排 |
| `backend/app/services/agentic/query_understanding.py` | **新增** | 458 | 双模式查询解析（正则 + LLM） |
| `backend/app/services/agentic/guided_search.py` | **新增** | 197 | POI 软排序 + 引导 chips |
| `backend/app/services/property_service.py` | 修改 | +319 / -90 | UnitType-first 搜索 + 向量 DB 下推 |
| `backend/app/services/compare_scoring.py` | 修改 | +122 / -3 | POI 偏好注册 + 通用化距离计算 |

---

## 3. 记忆机制

### 3.1 结论：做了，且很完整（两层记忆 + 搜索审计）

### 3.2 记忆架构

```
┌─────────────────────────────────────────┐
│          Agent 记忆体系                  │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │  会话短期状态（AgentSessionState）│    │
│  │  - 当前阶段(stage)               │    │
│  │  - 累积筛选条件(filters_json)    │    │
│  │  - 指代映射(reference_map_json)  │    │
│  │  - 上轮搜索结果(last_search)     │    │
│  │  - 滚动摘要(rolling_summary)     │    │
│  │  生命周期: 跟随 session          │    │
│  └─────────────────────────────────┘    │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │  账号长期偏好（AgentUserMemory）  │    │
│  │  - 国家/学校/房型等稳定字段      │    │
│  │  - 预算等临时字段（需重复验证）  │    │
│  │  - 置信度 + 证据计数             │    │
│  │  生命周期: 无 TTL，持久存储      │    │
│  └─────────────────────────────────┘    │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │  搜索审计（SearchRun+Candidate） │    │
│  │  - 原始查询 + 改写查询           │    │
│  │  - 有效条件 + 放宽轨迹           │    │
│  │  - 候选排名 + 分项分数 + 来源    │    │
│  │  生命周期: 无 TTL，持久存储      │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### 3.3 4 张新数据库表

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `agent_session_states` | 会话短期状态 | `session_id`(FK), `user_id`(FK), `stage`, `filters_json`(JSONB), `reference_map_json`(JSONB), `rolling_summary` |
| `agent_user_memories` | 用户跨会话偏好 | `user_id`(FK, unique), `preferences_json`(JSONB), `profile_summary` |
| `agent_search_runs` | 每次搜索审计 | `session_id`, `user_id`, `original_query`, `rewritten_query`, `effective_filters_json`, `relaxation_trace_json`, `latency_ms` |
| `agent_search_candidates` | 候选排名审计 | `search_run_id`(FK CASCADE), `unit_type_id`, `property_id`, `rank`, `final_score`, `score_breakdown_json`, `source_metadata_json` |

迁移文件：`backend/alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py`

另外：`chat_sessions` 表新增 `session_kind` 字段区分普通客服会话与 Agent 会话。

### 3.4 记忆规则

| 规则 | 说明 |
|------|------|
| 稳定字段快速固化 | 国家、学校、房型等首次表达即达跨会话阈值（起始置信度 0.78） |
| 临时字段需重复验证 | 预算等条件需在不同会话重复出现（起始置信度 0.55） |
| 应用阈值 | 置信度 ≥ 0.75 才会在后续会话中自动应用 |
| 去重 | 同一会话重复表达不会重复累计证据 |
| 手动保存 | 用户主动保存时置信度直接设为 1.0 |
| 重置风险 | "重新开始"会清空长期偏好（不只是当前会话），文档承认这是已知问题 |
| 开关控制 | `AGENT_MEMORY_ENABLED=false` 只关闭长期偏好应用/学习，会话状态和搜索审计仍生效 |

### 3.5 筛选合并优先级

```
账号长期偏好 < 当前会话状态 < 搜索页 context_filters < 本轮自然语言理解 < 前端显式 filters
```

列表条件默认增量合并，"取消""不要"才删除对应字段或列表值。

### 3.6 指代解析

支持跨轮指代：

- **序号引用**："第一套"、"第二套"（中文数字正则匹配）
- **语义引用**："最便宜"、"通勤最近"、"面积最大"、"综合最好"、"刚才那套"
- **事实追问**："这个有健身房吗" → 锁定上一轮具体房源，读取当前数据库字段，不再发起全局搜索

### 3.7 新增 API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/v1/agent/sessions` | 当前账号的 Agent 会话列表 |
| `GET` | `/api/v1/agent/sessions/{id}/messages` | 回放历史消息及元数据 |
| `GET` | `/api/v1/agent/memory` | 读取长期偏好 |
| `PUT` | `/api/v1/agent/memory` | 保存或替换长期偏好 |
| `DELETE` | `/api/v1/agent/memory` | 清空长期偏好 |
| `POST` | `/api/v1/agent/sessions/{id}/messages` | 非流式消息（支持 context_filters） |
| `POST` | `/api/v1/agent/sessions/{id}/messages/stream` | SSE 流式消息 |

---

## 4. 缓存机制

### 4.1 结论：有限缓存，Agent 搜索结果不做缓存

### 4.2 缓存现状全景

| 缓存项 | 存储 | TTL | 是否按账号隔离 | Agent 主链是否使用 |
|--------|------|-----|---------------|-------------------|
| 文本 → Embedding 向量 | Redis | 1 小时 | 否 | ✅ 是 |
| 旧版非向量房源筛选结果 | Redis | 5 分钟 | 否 | ❌ 否（Agent 绕过了它） |
| **Agent 搜索结果** | **不做缓存** | **N/A** | **N/A** | **每轮都查数据库** |
| Agent 会话状态 | PostgreSQL `agent_session_states` | 无 TTL | ✅ 是 | ✅ 是 |
| Agent 长期偏好 | PostgreSQL `agent_user_memories` | 无 TTL | ✅ 是 | ✅ 是 |
| 搜索轨迹和候选评分 | PostgreSQL search run/candidates | 无 TTL | ✅ 是 | ✅ 是 |
| 旧 Redis `SearchStateManager` | Redis | 2 小时 | 否 | ❌ 未实例化 |

### 4.3 Embedding 缓存细节

- 文件：`backend/app/services/embedding_cache.py`（已在 main 存在，PR 中整合）
- 匹配方式：文本 SHA256 精确匹配（前 16 位 hex）
- Key 格式：`emb:cache:v1:{sha256[:16]}`
- TTL：3600 秒（1 小时）
- 降级：Redis 不可用时静默降级，走实时 API 调用
- 连接：惰性连接 + 自动重连

### 4.4 为什么 Agent 搜索结果不做缓存

PR 文档明确说明："Agent 的房源结果不做结果缓存，每轮查询数据库"。旧有 Redis `SearchStateManager`（2 小时 TTL）虽在代码库中存在，但"当前 Agent 主链没有实例化或调用它"。

---

## 5. 侧边栏与搜索结果协同

### 5.1 协同架构

```
Search.vue (主页面)                    SearchAgentPanel.vue (侧边栏)
┌─────────────────────────┐            ┌──────────────────────────┐
│ 左侧筛选栏               │            │ AI 租房管家               │
│                         │            │                          │
│ 中间搜索结果区           │  props ──→│ 接收 filters, resultIds   │
│ ← show-recommendations  │←── emit ──│ 返回推荐结果               │
│ ← apply-filter-patch    │←── emit ──│ 返回筛选补丁               │
│                         │            │                          │
│ selectedResultIds ──────│── props ──→│ 用于对比候选              │
└─────────────────────────┘            └──────────────────────────┘
         │                                       │
         │              共享 Pinia Store          │
         └────────── agentChat (sessionId, ───────┘
                       messages, sessions)
                              │
                     agentService (SSE)
                              │
                     POST /api/v1/agent/
                     sessions/{id}/messages/stream
```

### 5.2 涉及的全部文件

#### 前端（直接参与协同）

| 文件 | 状态 | 行数 | 角色 |
|------|------|------|------|
| `frontend/src/components/search/SearchAgentPanel.vue` | **新增** | 843 | 右侧 AI 管家面板（核心组件） |
| `frontend/src/views/Search.vue` | 修改 | +618 | 三栏布局、Agent 开关、filter_patch 回填、推荐同步 |
| `frontend/src/views/AiSearch.vue` | 修改 | +749 | 全页 AI 找房（独立使用，非侧边栏模式） |
| `frontend/src/components/RecPropertyCard.vue` | **新增** | 398 | 推荐专用卡片（250px 宽，多币种） |
| `frontend/src/stores/agentChat.ts` | 修改 | +179 | 多会话管理、流式消息、长期偏好状态 |
| `frontend/src/services/agent.ts` | 修改 | +159 | SSE 流式客户端、会话/历史/记忆 API |
| `frontend/src/types/agent.ts` | 修改 | +139 | context_filters、filter_patch、推荐元数据类型 |
| `frontend/src/utils/currency.ts` | **新增** | 71 | 6 币种统一展示（CNY/GBP/SGD/USD/HKD/AUD） |
| `frontend/src/utils/agentRecommendations.ts` | **新增** | 55 | 推荐去重工具 |

#### 后端（必须联动）

| 文件 | 状态 | 行数 | 角色 |
|------|------|------|------|
| `backend/app/services/agentic/dispatcher.py` | 重写 | +1223 | 主链编排：接收 context_filters，生成 filter_patch |
| `backend/app/services/agentic/memory.py` | **新增** | 686 | 搜索页上下文与会话状态合并 |
| `backend/app/services/agentic/retrieval.py` | **新增** | 456 | 混合召回 + 重排 |
| `backend/app/services/agentic/query_understanding.py` | **新增** | 458 | 条件提取 + 查询改写 |
| `backend/app/services/agentic/context.py` | **新增** | 147 | 历史打包 + Grounded 事实边界 |
| `backend/app/services/agentic/guided_search.py` | **新增** | 197 | POI 软重排 + 引导选项 |
| `backend/app/api/v1/routes/agent.py` | 修改 | +367 | 新端点 + context_filters 透传 + filter_patch 序列化 |
| `backend/app/schemas/agent.py` | 修改 | +115 | context_filters、filter_patch、扩展推荐合同 |
| `backend/app/models/agent_intelligence.py` | **新增** | 124 | 4 张 Agent 表 ORM 模型 |

### 5.3 SearchAgentPanel 接口

```typescript
// 组件接收的 Props
const props = defineProps<{
  filters: AgentFilters        // 当前左侧筛选条件
  resultCount: number          // 当前可见结果数
  resultIds: number[]          // 当前可见结果的 ID 列表
  selectedResultIds: number[]  // 用户在左侧勾选的房源 ID
}>()

// 组件对外的事件
const emit = defineEmits<{
  (event: 'close'): void
  (event: 'apply-filter-patch', patch: Record<string, unknown>, refreshResults?: boolean): void
  (event: 'show-recommendations', recommendations: AgentRecommendation[]): void
}>()
```

### 5.4 协同关键逻辑

**Search → Sidebar（数据下发）：**

1. `agentFilters`（computed）：将 Search.vue 的筛选状态翻译为 `AgentFilters` 格式
   - 设施名称映射（50+ 条中文→英文白名单）
   - 学校模式检测
   - 租期档位编码
2. `agentComparableResults`（computed）：返回用户当前可见的房源列表
   - 地图模式 → 全部筛选结果
   - 列表模式 → 当前分页结果

**Sidebar → Search（结果回传）：**

1. `apply-filter-patch(patch)`：200+ 行的筛选回填函数
   - 国家别名映射（SG/Singapore/新加坡 → "SG"）
   - 数值字段（price_min, price_max, bedrooms）
   - 房型标准化（studio/ensuite/shared）
   - 设施映射（中文 → features/amenities/location_tags 三组）
   - 学校 ID 映射（UCLA/NUS/NTU → 硬编码 ID）
   - 通勤时间档位（5/10/15/20/30 min）
   - 租期分类（短/中/长租）

2. `show-recommendations(recommendations)`：将 Agent 推荐写入搜索结果
   - 调用 `propertyStore.setSearchResults(results)` 替换当前展示
   - 设置 `fromAgent = true` 标记
   - 有推荐时**不触发普通搜索**（防止覆盖 Agent 排序）
   - 无推荐时才在应用 filter_patch 后触发普通搜索

### 5.5 响应式布局断点

| 视口宽度 | Agent 展示方式 | 宽度 |
|----------|---------------|-----:|
| > 1360px | 三栏并排 | 390px |
| 1101px - 1360px | 三栏并排 | 350px |
| ≤ 1100px | 右侧覆盖抽屉 + 遮罩 | min(400px, 100vw) |
| ≤ 900px | 主搜索区单列 + 覆盖抽屉 | 最大视口宽度 |

### 5.6 filter_patch 规则

| 规则 | 说明 |
|------|------|
| 硬条件回填 | 明确的、可结构化的条件写入 `filter_patch` |
| 软偏好不回填 | "最好""尽量""优先"等不写回左侧筛选栏 |
| null 清除 | 用户取消条件时返回该字段为 `null` |
| 白名单限制 | 只返回 14 个白名单字段，防止任意修改 |
| 后端白名单字段 | `district, price_min, price_max, bedrooms, property_type, amenities, room_type, min_lease_months, max_lease_months, available_from, institution, commute_minutes` |

---

## 6. 侧边栏嫁接可行性分析

### 6.1 结论：**不能直接嫁接，需要合并整个 Agent Memory/RAG 基础设施**

### 6.2 为什么不能单独摘组件

`SearchAgentPanel.vue` 虽然接口干净（4 props + 3 emits），但它依赖的链条太长：

```
SearchAgentPanel.vue
  ├── agentChat Store (Pinia)
  │     ├── ensureSession()       ← 需要后端 POST /sessions
  │     ├── sendMessageStream()   ← 需要后端 SSE 端点
  │     ├── fetchSessions()       ← 需要后端 GET /sessions
  │     └── fetchMemory()         ← 需要后端 GET /memory
  ├── agentService
  │     └── sendMessageStream()   ← 需要后端返回 filter_patch + recommendations
  ├── types/agent.ts
  │     ├── AgentFilters          ← 新增 15+ 字段
  │     ├── AgentRecommendation   ← 新增 rank, final_score, score_breakdown
  │     ├── AgentStreamMeta       ← 新类型
  │     └── QueryRewriteInfo 等   ← 5+ 新类型
  ├── utils/currency.ts           ← 新增文件
  └── utils/agentRecommendations.ts ← 新增文件
            │
            ▼ 所有前端依赖最终都需要后端支持
            │
POST /api/v1/agent/sessions/{id}/messages
  └── dispatcher.py (1223行重写)
        ├── memory.py (4张新表)
        ├── query_understanding.py
        ├── retrieval.py
        ├── context.py
        └── search_agent.py (管线重写)
```

### 6.3 如果强行嫁接会发生什么

| 症状 | 原因 |
|------|------|
| TypeScript 编译失败 | `AgentFilters`、`AgentRecommendation` 等类型缺字段 |
| 运行时报错 | `currency.ts`、`agentRecommendations.ts` 文件不存在 |
| API 返回无 filter_patch | 后端 dispatcher 未升级，不理解 context_filters |
| SSE 流式不工作 | `sendMessageStream()` 依赖新的 SSE 端点 |
| 会话无法创建 | `ensureSession()` 依赖后端设置 `session_kind="agent"` |

### 6.4 推荐的嫁接路径

必须按以下顺序完整合入（来自 PR 文档自身的建议）：

```
第 1 步：数据库层
  ├── backend/alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py
  ├── backend/app/models/agent_intelligence.py
  └── backend/app/models/__init__.py（注册新模型）

第 2 步：后端 Agent Memory/RAG 主链
  ├── backend/app/services/agentic/memory.py
  ├── backend/app/services/agentic/context.py
  ├── backend/app/services/agentic/query_understanding.py
  ├── backend/app/services/agentic/retrieval.py
  ├── backend/app/services/agentic/guided_search.py
  └── backend/app/services/agentic/agents/search_agent.py（重写）

第 3 步：后端 API + Schema
  ├── backend/app/schemas/agent.py
  ├── backend/app/api/v1/routes/agent.py
  └── backend/app/services/agentic/dispatcher.py（重写）

第 4 步：前端类型 + 服务层
  ├── frontend/src/types/agent.ts
  ├── frontend/src/services/agent.ts
  ├── frontend/src/utils/currency.ts
  └── frontend/src/utils/agentRecommendations.ts

第 5 步：前端 Store + 组件
  ├── frontend/src/stores/agentChat.ts
  ├── frontend/src/components/search/SearchAgentPanel.vue
  ├── frontend/src/components/RecPropertyCard.vue
  └── frontend/src/views/Search.vue（集成三栏布局）
```

### 6.5 嫁接的工作量估算

| 任务 | 估时 | 说明 |
|------|-----:|------|
| 数据库迁移 | 0.5h | 跑 alembic upgrade head |
| 后端主链合入 | 3-4h | 5 个新文件 + search_agent 重写 + dispatcher 重写，需解决合并冲突 |
| 后端 API 适配 | 1-2h | schema + route，需确认与现有端点兼容 |
| 前端合同层 | 1h | types + services + utils，相对独立 |
| 前端组件集成 | 2-3h | SearchAgentPanel + RecPropertyCard + Search.vue 改造，applyAgentFilterPatch 需针对现有筛选 UI 适配 |
| 联调测试 | 2-3h | 完整用户流程验证 |
| **合计** | **10-14h** | 相当于合并整个 PR 的 Agent 部分 |

---

## 7. 文件级合并清单

### 7.1 必须一起合并（核心依赖链）

```
backend/
  alembic/versions/20260725_0100_embedding_vector_hnsw.py    ← HNSW 索引（PR 早期 commit）
  alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py  ← 4 张新表
  app/models/agent_intelligence.py                            ← ORM 模型
  app/models/__init__.py                                      ← 注册模型
  app/models/chat.py                                          ← session_kind 字段
  app/core/config.py                                          ← Agent 配置项
  app/db/session.py                                           ← 连接池参数
  app/schemas/agent.py                                        ← 扩展合同
  app/api/v1/routes/agent.py                                  ← 新端点 + 扩展序列化
  app/services/agentic/dispatcher.py                          ← 主链编排
  app/services/agentic/memory.py                              ← 记忆服务
  app/services/agentic/context.py                             ← 上下文打包
  app/services/agentic/query_understanding.py                 ← 查询理解
  app/services/agentic/retrieval.py                           ← 混合召回+重排
  app/services/agentic/guided_search.py                       ← 引导搜索
  app/services/agentic/agents/search_agent.py                 ← 搜索管线
  app/services/agentic/agents/compare_agent.py                ← 对比流式化
  app/services/agentic/shared.py                              ← 通用工具
  app/services/property_service.py                            ← UnitType-first 搜索
  app/services/embedding_service.py                           ← Embedding 缓存整合
  app/services/chat_service.py                                ← session_kind 支持
  app/services/comparison_service.py                          ← 去 ReAct
  app/services/compare_scoring.py                             ← POI 偏好扩展
  app/services/currency.py                                    ← 多币种支持
  tests/test_agent_filter_patch.py                            ← filter_patch 测试
  tests/test_agent_intelligence.py                            ← Agent 主链测试
  tests/test_agent_streaming.py                               ← 流式测试
  tests/test_agent_user_scenarios.py                          ← 用户场景测试

frontend/
  src/types/agent.ts                                          ← 扩展类型
  src/services/agent.ts                                       ← SSE + 新端点
  src/stores/agentChat.ts                                     ← 多会话+记忆状态
  src/utils/currency.ts                                       ← 多币种工具（新增）
  src/utils/agentRecommendations.ts                           ← 推荐去重（新增）
  src/components/search/SearchAgentPanel.vue                  ← 侧边栏面板（新增）
  src/components/RecPropertyCard.vue                          ← 推荐卡片（新增）
  src/views/Search.vue                                        ← 三栏集成
  src/views/AiSearch.vue                                      ← 全页 AI 搜索
  src/views/SmartRentView.vue                                 ← 合同升级适配
  src/views/CompareView.vue                                   ← 对比页重写
```

### 7.2 不应顺带合并（属于 PR 工作区的无关改动）

```
frontend/src/views/Home.vue                  ← 首页补充，非 Agent
frontend/src/router/index.ts                 ← 预订路由 + 政策页，非 Agent
frontend/src/services/profile.ts             ← 个人中心统计，非 Agent（新增）
frontend/src/utils/orderPresentation.ts      ← 订单工具，非 Agent（新增）
frontend/src/utils/paymentResult.ts          ← 支付工具，非 Agent（新增）
frontend/src/utils/profileSelection.ts       ← 个人中心工具，非 Agent（新增）
frontend/src/utils/profileSummary.ts         ← 个人中心工具，非 Agent（新增）
frontend/src/views/policies/                 ← 政策页面，非 Agent
backend/test/TEST_GUIDED_SEARCH.html         ← 手动测试页，非必须
backend/scripts/seed_agent_demo.py           ← 演示数据脚本，非运行时必须
```

### 7.3 建议的提交拆分

```
feat(db): 新增 Agent 会话记忆与搜索追踪表
feat(backend): 支持搜索页条件上下文与筛选回填
feat(frontend): 在房源搜索页接入右侧 Agent 面板
test(search): 补充 Agent 筛选回填规则测试
docs(search): 补充三栏 Agent 合并指南
```

---

## 附录：PR 提交时间线

| 日期 | 提交 | 说明 |
|------|------|------|
| 2026-07-27 | `2d57d96` | Agent 搜索与对比模块基础升级（HNSW、cosine、向量缓存） |
| 2026-07-29 | `4bd4a36` | 修复 main 合并损坏（模型导入/Property映射/路由挂载） |
| 2026-07-29 | `6f00d3b` | 渐进选房前端接通 + AI 回复真流式 + 短提示词 + 推荐卡片 |
| 2026-07-29 | `5ec57a4` | 综合对比 ReAct 循环重写为单次 LLM 调用 |
| 2026-07-29 | `3f0bee1` | 推荐提示词恢复口语化长文版 |
| 2026-08-05 | `7d4d39e` | 完善智能检索、流式交互与房源对比 |
| 2026-08-05 | `d089cb9` | 按户型表过滤房源 |

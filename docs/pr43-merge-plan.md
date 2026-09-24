# PR #43 逐部分合并方案（细化版）

> 编写日期：2026-08-05
> 目标：将 PR #43 的全部 Agent 开发进度，拆分为独立可合并的单元，逐部分嫁接到当前 HEAD (`9bc1f48`)
> 合并原则：**所有 AI/Agent 逻辑优先使用 PR #43 的实现。HEAD 已有的非 Agent 代码保留不动。**
> 核心冲突：HEAD 已完成 Room 表删除（三层→两层），PR #43 假设 `properties` 表仍存在

---

## 合并单元总览

```
Unit  1  数据库基础           Unit 11  API + Schema
Unit  2  共享工具层           Unit 12  PropertyService
Unit  3  查询理解             Unit 13  EmbeddingService
Unit  4  记忆系统             Unit 14  CompareService
Unit  5  上下文管理           Unit 15  前端类型层
Unit  6  检索与排序           Unit 16  前端工具层
Unit  7  引导搜索             Unit 17  前端服务层
Unit  8  SearchAgent 重写     Unit 18  前端状态层
Unit  9  CompareAgent 升级    Unit 19  前端组件层
Unit 10  Dispatcher 重写      Unit 20  前端视图层
```

---

## Unit 1：数据库基础

### 1.1 `backend/app/models/agent_intelligence.py` — **新增，直接复制**

全新文件，4 张 Agent 表的 ORM 模型。零冲突。

```bash
git show FETCH_HEAD:backend/app/models/agent_intelligence.py > backend/app/models/agent_intelligence.py
```

### 1.2 `backend/app/models/__init__.py` — **合并，只加 Agent 模型导入**

**冲突：** PR #43 导入了 `Room, Property` 等旧模型名，还引用了 HEAD 已删除的 `NotificationChannel/DeliveryStatus`。

**解决：** 不从 PR #43 整文件覆盖。只在 HEAD 现有的 `__init__.py` 中追加这 4 行：

```python
from app.models.agent_intelligence import (
    AgentSearchCandidate,
    AgentSearchRun,
    AgentSessionState,
    AgentUserMemory,
)
```

然后在 `__all__` 列表末尾追加这 4 个类名。**不碰 HEAD 已有的任何导入。**

### 1.3 `backend/alembic/versions/20260725_0100_embedding_vector_hnsw.py` — **新增，但要改**

**冲突：** PR #43 给 `properties` 和 `unit_types` **两张表**建 embedding 列和 HNSW 索引。HEAD 已无 `properties` 表。

**解决：** 复制迁移文件，删除所有 `properties` 相关的操作：

```python
# 只保留这一段：
for table in ("unit_types",):  # 原代码: ("properties", "unit_types")
    _text_to_vector(table)

# 删除：CREATE INDEX ... ON properties USING hnsw ...
# 保留：CREATE INDEX ... ON unit_types USING hnsw ...
```

`unit_types` 表可能已经有 `embedding` 列 — 迁移中加 `IF NOT EXISTS` 风格的检查，或用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`。

### 1.4 `backend/alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py` — **新增，改 FK 目标**

**冲突：** `agent_search_candidates` 表的 `property_id` FK 指向 `properties(id)`。HEAD 没有 `properties` 表。

**解决：** 复制迁移文件，修改：

```python
# 原：
sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="SET NULL"))

# 改为：
sa.Column("property_id", sa.Integer(), sa.ForeignKey("unit_types.id", ondelete="SET NULL"))
```

其他表（`agent_session_states`, `agent_user_memories`, `agent_search_runs`）和 `chat_sessions.session_kind` 列不变。

### 1.5 `backend/app/models/chat.py` — **合并，只加 session_kind 字段**

**冲突：** HEAD 有自己的 `chat.py`。PR #43 只新增了一个字段。

**解决：** 在 HEAD 的 `ChatSession` 类中加一行：

```python
session_kind: Mapped[str] = mapped_column(String(32), default="chat", nullable=False, index=True)
```

### 1.6 `backend/app/core/config.py` — **合并，只加 Agent 配置项**

**冲突：** HEAD 有自己的 `config.py`。

**解决：** 在 HEAD 文件的 `Settings` 类末尾追加 7 个字段：

```python
agent_memory_enabled: bool = True
agent_retrieval_pool_size: int = 120
agent_min_results: int = 3
agent_history_char_budget: int = 8000
agent_context_char_budget: int = 12000
agent_recommend_temperature: float = 0.35
# 以下 3 个是 PR #43 的 db session 配置，HEAD 可能已有
db_pool_size: int = 20
db_max_overflow: int = 10
db_pool_timeout: int = 30
```

同步更新 `.env.example`。

### 1.7 `backend/app/db/session.py` — **合并，只加连接池参数**

**冲突：** HEAD 有自己的 `session.py`。

**解决：** 确认 `create_async_engine` 调用是否已有这些参数，没有则追加：

```python
pool_size=settings.db_pool_size,
max_overflow=settings.db_max_overflow,
pool_timeout=settings.db_pool_timeout,
pool_recycle=1800,
pool_pre_ping=True,
```

### 1.8 其他 model 文件的 JSONB/ARRAY 兼容性修改 — **跳过**

PR #43 给 Booking/Contract/Institute/Notification/Payment/Property/RoomType/UnitType/University 等模型加了 SQLite JSON variant。这是为 SQLite 测试环境准备的。**如果 HEAD 的测试已经通过，跳过这些改动。**

---

## Unit 2：共享工具层

### 2.1 `backend/app/services/agentic/shared.py` — **合并，加新函数，不动旧函数**

**冲突：** HEAD 有自己的 `shared.py`（可能包含 `property_to_dict`、`get_symbol` 等已有函数）。PR #43 新增了 5 个函数。

**解决：** 保持 HEAD 已有函数不动，从 PR #43 追加以下函数到文件末尾：

```python
# 从 PR #43 复制以下函数（不改动 HEAD 已有内容）：
property_currency(prop)          # 取房源币种，默认 CNY
format_property_money(prop, n)   # 格式化金额 + 正确币种符号
comparable_price_cny(prop)       # 统一换算为 CNY 做跨币种比较
_amenity_list(value)             # 设施解析（list/JSON字符串/逗号分隔）
property_amenities(prop)         # 设施合并去重
```

⚠️ `property_amenities()` 在 PR #43 中合并三层（Property+UnitType+Institute）。HEAD 中 Property=UnitType，改为两层合并：

```python
def property_amenities(prop) -> set[str]:
    """合并 UnitType 和 Institute 的设施，去重。"""
    values = []
    # HEAD: prop 即是 UnitType
    if hasattr(prop, 'amenities') and prop.amenities:
        values.extend(prop.amenities)
    # Institute 通过 property.institute 关系取
    inst = getattr(prop, 'institute', None)
    if inst and hasattr(inst, 'amenities') and inst.amenities:
        values.extend(inst.amenities)
    return set(_amenity_list(v) for v in values if _amenity_list(v))
```

### 2.2 `backend/app/services/currency.py` — **合并，只加 AUD**

**解决：** 在 HEAD 文件的汇率字典中追加 AUD 条目：

```python
"AUD": {"rate": 4.70, "symbol": "A$", "label": "澳元"},
```

---

## Unit 3：查询理解 `query_understanding.py` — **新增，直接复制**

全新文件 458 行。零冲突。

```bash
git show FETCH_HEAD:backend/app/services/agentic/query_understanding.py > backend/app/services/agentic/query_understanding.py
```

依赖：LLM service（已有）、Unit 2 的币种/国家工具。

---

## Unit 4：记忆系统 `memory.py` — **新增，直接复制**

全新文件 686 行。零冲突。

```bash
git show FETCH_HEAD:backend/app/services/agentic/memory.py > backend/app/services/agentic/memory.py
```

依赖：Unit 1 的 4 张表、Unit 2 的 shared 工具。

---

## Unit 5：上下文管理 `context.py` — **新增，直接复制**

全新文件 147 行。零冲突。

```bash
git show FETCH_HEAD:backend/app/services/agentic/context.py > backend/app/services/agentic/context.py
```

⚠️ `load_packed_history()` 查询 `chat_messages` 表。确认 HEAD 表结构与 PR #43 一致，特别是有 `metadata_` JSONB 列和 `role` 列。

---

## Unit 6：检索与排序 `retrieval.py` — **新增，直接复制**

全新文件 456 行。零冲突。

```bash
git show FETCH_HEAD:backend/app/services/agentic/retrieval.py > backend/app/services/agentic/retrieval.py
```

⚠️ `candidate_matches_filters()` 访问 `item["unit_type"]` 和 `item["institute"]` 对象。HEAD 的 UnitType 模型与 PR #43 的字段名确认一致（`base_rent`, `bedrooms`, `bathrooms`, `area_sqm`, `amenities`, `min_stay_months`, `currency`, `available_from`）。

---

## Unit 7：引导搜索 `guided_search.py` — **新增，直接复制**

全新文件 197 行。零冲突。

```bash
git show FETCH_HEAD:backend/app/services/agentic/guided_search.py > backend/app/services/agentic/guided_search.py
```

⚠️ `attach_poi_distances()` 在 PR #43 中通过 Room→UnitType 桥接。HEAD 无 Room 表，改为直接通过 UnitType.id 查 `PropertyPOI` 表。这个改动在 Unit 7 内部就能完成，不涉及其他文件。

---

## Unit 8：SearchAgent 重写

### 策略：**用 PR #43 版本全面替换 HEAD 版本，然后删除不适用部分**

### 8.1 整体操作

```bash
# 用 PR #43 版本覆盖 HEAD
git show FETCH_HEAD:backend/app/services/agentic/agents/search_agent.py > backend/app/services/agentic/agents/search_agent.py
```

### 8.2 然后删除以下代码块

**A. 旧数据兼容层 — 全部删除（HEAD 无 properties 表）**

| 删除项 | 行号（在 PR #43 文件中） | 原因 |
|--------|------------------------|------|
| `class _LegacyUnitView` | ~65-82 | 为旧 properties 行捏造 UnitType 形状，HEAD 不需要 |
| `class _LegacyInstituteView` | ~84-99 | 为旧 properties 行捏造 Institute 形状，HEAD 不需要 |
| `_parse_legacy_amenities()` | ~101-113 | 解析旧表 JSON/逗号文本设施格式，HEAD 不需要 |
| `_legacy_candidate()` | ~116-170 | 把旧 properties 行投影为候选 dict，HEAD 不需要 |
| `_legacy_recall()` | ~574-597 | 专门查旧 properties 表，HEAD 不需要 |

**B. `_pipeline()` 中的 fallback 调用 — 删除**

```python
# 删除这段（约在 _pipeline() 末尾）：
# if not recall_pool and not requires_school_clarification:
#     legacy_strict = await self._legacy_recall(active_filters, limit=pool_limit)
#     ...
```

改为：
```python
# 如果 recall_pool 为空，直接返回空结果 + 放宽建议
if not recall_pool:
    return {"reply": "未找到匹配的房源，请尝试放宽条件。", "recommendations": [], ...}
```

**C. ReAct facade — 删除**

```python
# 删除 search_react() 方法（PR #43 中已降级为 facade，HEAD 不需要）
```

同时从 `tools` 列表中删除 ReAct 相关工具名。HEAD 已有 `search_react` 的逻辑全部丢弃，Dispatcher（Unit 10）不再走 ReAct 路径。

**D. HEAD 独有的旧函数 — 不在 PR #43 文件中，无需操作**

PR #43 版本覆盖后，以下 HEAD 旧函数自然消失（这正是我们想要的）：

| HEAD 旧函数 | 被 PR #43 的什么替代 |
|------------|-------------------|
| `build_search_text(room)` | `build_unit_type_search_text(institute, unit_type)` |
| `_describe_neighborhood()` | `context.py` 的 grounded context |
| `_describe_safety()` | `context.py` 的 grounded context |
| `score_properties()` | `retrieval.py` 的 `rerank_candidates()` |
| `_props_text()` | `context.py` 的 `pack_grounded_candidates()` |
| `_lookup_institution()` | 保留（PR #43 也有） |
| `_build_search_kwargs()` | 废弃，条件构建移到 `retrieval.py` |
| `_build_source_info()` | 废弃，来源追踪移到 `context.py` |
| `validate_recommendations()` | 废弃，验证移到 `context.py` 的 grounding_policy |

### 8.3 确认保留的内容

- `build_unit_type_search_text()` — PR #43 的主线 embedding 文本构建
- `generate_unit_type_embedding()` — PR #43 和 HEAD 都有，保留 PR #43 版本
- `RECOMMEND_SYSTEM_PROMPT` — PR #43 的口语化四段式提示词
- `_infer_currency()` — HEAD 有，PR #43 也有，保留 PR #43 版本
- `_lookup_commute()` — HEAD 有，PR #43 也有，保留 PR #43 版本

---

## Unit 9：CompareAgent 升级

### 策略：**PR #43 版本覆盖，然后改 Room→UnitType 引用**

### 9.1 整体操作

```bash
git show FETCH_HEAD:backend/app/services/agentic/agents/compare_agent.py > backend/app/services/agentic/agents/compare_agent.py
```

### 9.2 修改点

**`_load_properties()` 方法：**

```python
# PR #43 原代码查 Property 表（即 properties 表）：
# stmt = select(Property).where(Property.id.in_(ordered_ids))

# 改为查 UnitType：
stmt = select(UnitType).where(UnitType.id.in_(ordered_ids))
```

同时把函数内所有 `Property` 引用改为 `UnitType`，`prop.unit_type` 的访问改为直接用 `prop`（因为 Property 即 UnitType）。

---

## Unit 10：Dispatcher 重写

### 策略：**PR #43 版本全面替换 HEAD 版本**

### 10.1 整体操作

```bash
git show FETCH_HEAD:backend/app/services/agentic/dispatcher.py > backend/app/services/agentic/dispatcher.py
```

HEAD 的 dispatcher（244 行简单 if/elif 路由）完全被替换为 PR #43 的编排管线（1102 行）。

### 10.2 确认以下依赖在 HEAD 中存在

```python
from app.services.agentic.agents.search_agent import SearchAgent   # Unit 8 替换后存在
from app.services.agentic.agents.compare_agent import CompareAgent # Unit 9 替换后存在
from app.services.agentic.agents.cart_agent import CartService     # HEAD 已有
from app.services.agentic.agents.filter_agent import ...           # HEAD 已有
from app.services.agentic.router import classify_message           # HEAD 已有
from app.services.agent_faq import match_faq, get_faq             # 确认 HEAD 有
```

### 10.3 确认数据库字段存在

`_persist_messages()` 写入 `chat_messages.metadata_` 字段。确认 HEAD 的 `chat_messages` 表有此 JSONB 列。如果没有，在 Unit 1 的迁移中补上。

### 10.4 确认 HEAD 不需要改动的部分

- `_StepRecorder` — 新增，直接保留
- `_DispatchContext` — 新增，直接保留
- `_prepare_context()` — 新增，记忆恢复+意图分类+指代解析
- `_prepare_search()` — 新增，查询理解+筛选合并+位置守卫
- `_execute_search()` — 新增，管线搜索+LLM生成+filter_patch
- `_execute_non_search()` — 新增，compare/cart/faq/general 分支
- `_build_filter_patch()` — 新增，筛选回填

---

## Unit 11：API + Schema

### 11.1 `backend/app/schemas/agent.py` — **合并，PR #43 版本为主体**

**策略：** 取 PR #43 版本，然后验证与 HEAD 现有 API 消费者的兼容性。

```bash
git show FETCH_HEAD:backend/app/schemas/agent.py > backend/app/schemas/agent.py
```

然后检查 HEAD 中哪些地方引用了旧的 `AgentMessageRequest` / `AgentMessageResponse`。PR #43 是**加字段**（`context_filters`、`filter_patch` 等），不删旧字段，所以向后兼容。

### 11.2 `backend/app/api/v1/routes/agent.py` — **合并，保留 HEAD 已有端点，加 PR #43 新端点**

**冲突：** HEAD 已有 agent 路由文件。PR #43 新增了 7 个端点。

**解决：** 取 PR #43 版本覆盖，然后检查：

1. HEAD 中是否有 PR #43 不存在的自定义端点 → 保留
2. PR #43 新增的端点（sessions 列表、历史回放、memory CRUD、SSE 流式）→ 全部保留
3. POST `/sessions/{id}/messages` 中新增的 `context_filters` 和 `mode` 参数 → 保留
4. 响应序列化中的 `_to_search_result()` 和 `_serialize_meta()` → 用 PR #43 版本（处理 UnitType 真实字段）

```bash
git show FETCH_HEAD:backend/app/api/v1/routes/agent.py > backend/app/api/v1/routes/agent.py
# 然后对比 HEAD 版本，找回 HEAD 独有的端点（如果有的话）
```

### 11.3 `backend/app/api/v1/router.py` — **不覆盖，只确认路由注册**

PR #43 修改了 `router.py`（+18/-6）。**不直接覆盖 HEAD。** 只确认 agent 路由已注册：

```python
# HEAD 应该已有此行，没有则加上：
api_router.include_router(agent_router, prefix="/agent", tags=["AI Agent"])
```

---

## Unit 12：PropertyService 升级

### 策略：**用 PR #43 的 `search_unit_types()` 替换 HEAD 版本，删除旧兼容层**

### 12.1 `search_unit_types()` — **用 PR #43 版本，改库存聚合**

PR #43 的 `search_unit_types()` 核心升级是 pgvector `cosine_distance` 在 SQL 内完成。但 JOIN `rooms` 做库存聚合的部分需要改。

```python
# PR #43 原代码：
# .outerjoin(Room, Room.unit_type_id == UnitType.id)
# func.count(Room.id).label("available_rooms")

# 改为直接取 UnitType 自身状态：
# available_rooms = 1 if UnitType.status == 'available' else 0
```

具体修改 `property_service.py` 中 `search_unit_types()` 函数的返回结构：

```python
# 原返回：{"unit_type": UnitType实例, "institute": Institute实例, "available_rooms": N, ...}
# 新返回：{"unit_type": UnitType实例, "institute": Institute实例, "available_rooms": 1, ...}
# available_rooms 固定为 1（每个 UnitType 即一个可租单元）
```

### 12.2 删除旧兼容层

以下 PR #43 中的函数全部删除（HEAD 无 `properties` 表）：

```python
# 删除：
_legacy_read_options()
_LegacyUnitView        # 注意：search_agent.py 中也有同名 dataclass，两处都删
_LegacyInstituteView
_apply_legacy_defaults()
```

### 12.3 区域匹配扩展 — **保留**

PR #43 扩展了区域匹配为多字段搜索（district/city/country/name/name_cn）+ 国家别名。这是纯 SQL 改进，无 Room 依赖，直接保留。

---

## Unit 13：EmbeddingService 升级

### 策略：**在 HEAD 现有版本上追加 PR #43 的缓存层**

### 13.1 不覆盖 HEAD 的 `embedding_service.py`

HEAD 已有 `EmbeddingService` 类。PR #43 新增了 Redis 缓存包装。

**解决：** 从 PR #43 提取以下内容，追加到 HEAD 文件：

```python
# 1. EmbeddingCache 类（约 95 行）
# 2. get_embedding_service() 模块级单例
# 3. generate_embedding() 中的缓存检查逻辑：
#    cached = await self._cache.get(text)
#    if cached: return cached
#    vec = await self._do_embed(text)
#    await self._cache.set(text, vec)
#    return vec
```

不覆盖 HEAD 已有的 API 签名和模型初始化逻辑。

---

## Unit 14：CompareService 去 ReAct

### 14.1 `backend/app/services/comparison_service.py` — **用 PR #43 版本覆盖**

```bash
git show FETCH_HEAD:backend/app/services/comparison_service.py > backend/app/services/comparison_service.py
```

PR #43 删除了所有 ReAct 工具定义和执行器（-319 行），改为单次 LLM 调用（+100 行）。HEAD 如果还在用 ReAct 对比，这正是要替换的。

### 14.2 `backend/app/services/compare_scoring.py` — **用 PR #43 版本覆盖**

```bash
git show FETCH_HEAD:backend/app/services/compare_scoring.py > backend/app/services/compare_scoring.py
```

新增 POI 偏好注册表 + 通用化距离计算。纯增量，无冲突。

---

## Unit 15：前端类型层

### 策略：**PR #43 新增字段追加到 HEAD 现有类型**

### 15.1 `frontend/src/types/agent.ts`

**不覆盖 HEAD。** 在 HEAD 现有文件基础上追加 PR #43 新增的内容：

```typescript
// 追加到文件末尾：

// 新增接口（从 PR #43 完整复制）：
export interface AgentSessionSummary { ... }
export interface AgentHistoryMessage { ... }
export interface AgentMemory { ... }
export interface AgentStreamMeta { ... }
export interface QueryRewriteInfo { ... }
export interface AgentStateChip { ... }
export interface AgentStateSummary { ... }
export interface ReferenceResolutionInfo { ... }
export interface GuidedOption { ... }
export interface AgentSource { ... }

// 已有接口的字段扩展（只加字段，不动已有字段）：
// AgentFilters: +currency, amenities, bathrooms, room_type, institution,
//                commute_mode, commute_minutes, area_min, area_max,
//                min_lease_months, max_lease_months, available_from,
//                female_only, poi_requirements
// AgentRecommendation: +rank, final_score, score_breakdown, poi_distances, source_metadata
// AgentChatMessage: +id, guidedOptions, stateSummary, queryRewrite, sources,
//                    filterPatch, streaming, isWelcome
// AgentMessageResponse: +guided_options, raw_intent, stage, sources,
//                        relaxation_trace, query_rewrite, reference_resolution,
//                        state_summary, filter_patch
```

### 15.2 `frontend/src/types/property.ts`

PR #43 新增了少量字段（+2 行）。在 HEAD 文件上追加即可。

---

## Unit 16：前端工具层 — **全部新增，直接复制**

```bash
git show FETCH_HEAD:frontend/src/utils/currency.ts > frontend/src/utils/currency.ts
git show FETCH_HEAD:frontend/src/utils/agentRecommendations.ts > frontend/src/utils/agentRecommendations.ts
```

两个文件都是 HEAD 中不存在的全新文件。零冲突。

---

## Unit 17：前端服务层

### 策略：**PR #43 新增方法追加到 HEAD 现有 service**

### 17.1 `frontend/src/services/agent.ts`

**不覆盖 HEAD。** 在 HEAD 现有 `agentService` 对象上追加 PR #43 新增的方法：

```typescript
// 追加方法（从 PR #43 提取）：
listSessions(limit, offset)           → GET  /agent/sessions
getSessionMessages(sessionId)         → GET  /agent/sessions/:id/messages
getMemory()                           → GET  /agent/memory
saveMemory(preferences, replace)      → PUT  /agent/memory
clearMemory()                         → DELETE /agent/memory
sendMessageStream(sessionId, body, handlers)  → POST /agent/sessions/:id/messages/stream (SSE)

// 已有方法签名扩展：
sendMessage() 的 body 参数 +context_filters, +mode
compareCart() 的参数 +poiPrefKeys
```

---

## Unit 18：前端状态层

### 策略：**PR #43 新增状态和方法追加到 HEAD 现有 Store**

### 18.1 `frontend/src/stores/agentChat.ts`

**不覆盖 HEAD。** 在 HEAD 现有 Store 上追加 PR #43 新增的内容：

```typescript
// 新增状态（追加到 store 定义中）：
const sessions = ref<AgentSessionSummary[]>([])
const loadingHistory = ref(false)
const rememberedPreferences = ref<AgentFilters>({})
const memoryLoaded = ref(false)

// 新增方法（追加到 return 中）：
function appendStreamingAssistant(initial?) { ... }
async function fetchSessions() { ... }
async function fetchMemory() { ... }
async function newSession() { ... }
async function switchSession(id) { ... }
async function saveMemory(preferences) { ... }
async function clearMemory() { ... }

// 已有方法签名扩展：
// sendMessage() 的 body 参数 +context_filters
```

---

## Unit 19：前端组件层 — **全部新增，直接复制**

```bash
# 创建目录（如果不存在）
mkdir -p frontend/src/components/search

# 复制新文件
git show FETCH_HEAD:frontend/src/components/search/SearchAgentPanel.vue > frontend/src/components/search/SearchAgentPanel.vue
git show FETCH_HEAD:frontend/src/components/RecPropertyCard.vue > frontend/src/components/RecPropertyCard.vue
```

两个文件都是 HEAD 中不存在的全新文件。零冲突。

依赖确认：
- `SearchAgentPanel.vue` 引用 `@/stores/agentChat`、`@/services/agent`、`@/types/agent`、`@/utils/currency`、`@/utils/agentRecommendations` → Unit 15-18 已处理
- `RecPropertyCard.vue` 引用 `@/types/agent`、`@/utils/image` → 已满足

---

## Unit 20：前端视图层

### 20.1 `frontend/src/views/Search.vue` — **手动合并，PR #43 的 Agent 三栏逻辑嫁接到 HEAD 页面**

**冲突：** 这是最重的冲突。HEAD 的 `Search.vue` 已有自己的修改（筛选、地图、分页），PR #43 新增了 Agent 侧边栏集成（+618 行）。

**解决（逐块操作，不整文件覆盖）：**

**第 1 步：模板区 — 加 Agent 按钮 + 侧边栏容器**

在 HEAD 的 `<template>` 中，结果区右上角加 Agent 开关按钮：
```html
<!-- 加在搜索结果 toolbar 区域 -->
<el-button @click="toggleAgent" :type="agentOpen ? 'primary' : 'default'">
  <el-icon><ChatDotRound /></el-icon> AI 租房管家
</el-button>
```

在 `.search-layout` 末尾（中间结果区后面）加侧边栏容器：
```html
<aside v-if="agentOpen" class="agent-dock" :class="{ 'agent-drawer': isNarrowScreen }">
  <Suspense>
    <SearchAgentPanel
      :filters="agentFilters"
      :result-count="agentComparableResults.length"
      :result-ids="agentComparableResults.map(p => p.id)"
      :selected-result-ids="selectedResultIds"
      @close="agentOpen = false"
      @apply-filter-patch="applyAgentFilterPatch"
      @show-recommendations="showAgentRecommendations"
    />
    <template #fallback>
      <div class="agent-loading">AI 管家启动中...</div>
    </template>
  </Suspense>
</aside>
```

**第 2 步：脚本区 — 加 Agent 相关的响应式状态和方法**

```typescript
// 追加到 <script setup> 中：

// ====== Agent 侧边栏 ======
import { defineAsyncComponent } from 'vue'
import type { AgentFilters, AgentRecommendation } from '@/types/agent'

const SearchAgentPanel = defineAsyncComponent(() => import('@/components/search/SearchAgentPanel.vue'))

const agentOpen = ref(false)
const fromAgent = ref(false)
const selectedResultIds = ref<number[]>([])
const agentContext = ref<string>('')

// 当前筛选 → Agent 可识别的格式
const agentFilters = computed<AgentFilters>(() => {
  // 从 HEAD 的 filters 对象翻译为 AgentFilters
  // 设施名称映射（使用 PR #43 的 _AGENT_AMENITY_LABELS）
  // 学校模式检测
  // 租期编码
  ...
})

// Agent 可比较的当前结果
const agentComparableResults = computed(() => {
  // 地图模式 → 全部筛选结果
  // 列表模式 → 当前分页结果
  ...
})

// 接收 Agent 筛选补丁 → 更新左侧筛选栏
function applyAgentFilterPatch(patch: Record<string, unknown>, refreshResults?: boolean) {
  // 200+ 行映射逻辑（从 PR #43 的 Search.vue 提取）：
  // - 国家别名 → filters.country
  // - 数值字段 → filters.priceMin/Max, filters.bedrooms
  // - 房型标准化
  // - 设施映射（白名单 → features/amenities/location_tags）
  // - 学校 ID → 学校搜索模式
  // - 通勤档位 → commuteTime
  // - 租期分类 → durationFilter
  ...
}

// 接收 Agent 推荐 → 替换搜索结果
function showAgentRecommendations(recommendations: AgentRecommendation[]) {
  const results = recommendations.map(rec => ({
    id: rec.property_id,
    // ... 映射为 Property 类型
  }))
  propertyStore.setSearchResults(results)
  fromAgent.value = true
}

// 切换 Agent 面板（需登录检查）
function toggleAgent() {
  if (!authStore.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  agentOpen.value = !agentOpen.value
}
```

**第 3 步：样式区 — 加三栏布局 CSS**

```css
/* 从 PR #43 的 Search.vue 提取 CSS */
.search-layout.agent-open {
  grid-template-columns: 260px 1fr 390px;
}
@media (max-width: 1360px) {
  .search-layout.agent-open {
    grid-template-columns: 260px 1fr 350px;
  }
}
@media (max-width: 1100px) {
  .agent-dock {
    position: fixed; right: 0; top: 0; bottom: 0; z-index: 100;
    width: min(400px, 100vw);
  }
}
/* ... 其余响应式断点 */
```

**第 4 步：在搜索结果卡片上加对比勾选框**

```html
<!-- 每个 PropertyCard 的角落 -->
<el-checkbox
  :model-value="selectedResultIds.includes(property.id)"
  @change="(checked) => toggleResultCompare(property.id, checked)"
/>
```

### 20.2 `frontend/src/views/AiSearch.vue` — **用 PR #43 版本覆盖，然后适配 HEAD 路由**

HEAD 可能叫 `AgentView.vue`。确认文件名和路由：

```bash
# 如果 HEAD 是 AgentView.vue：
git show FETCH_HEAD:frontend/src/views/AiSearch.vue > frontend/src/views/AgentView.vue
# 同时更新 router 中的 import 路径
```

PR #43 的 AiSearch.vue 是完全重写的（+749 行，两栏布局，会话历史，记忆卡）。用 PR #43 版本。

### 20.3 `frontend/src/views/CompareView.vue` — **用 PR #43 版本覆盖**

```bash
git show FETCH_HEAD:frontend/src/views/CompareView.vue > frontend/src/views/CompareView.vue
```

PR #43 完全重写了对比页（+1177 行，三 tab 布局）。用 PR #43 版本。

### 20.4 `frontend/src/views/SmartRentView.vue` — **用 PR #43 版本覆盖**

```bash
git show FETCH_HEAD:frontend/src/views/SmartRentView.vue > frontend/src/views/SmartRentView.vue
```

### 20.5 `frontend/src/router/index.ts` — **不覆盖，手动确认路由**

只确认以下路由存在，没有则加：
```typescript
{ path: '/ai-search', name: 'AiSearch', component: () => import('@/views/AiSearch.vue') }  // 或 AgentView.vue
{ path: '/compare', name: 'Compare', component: () => import('@/views/CompareView.vue') }
```

**不从 PR #43 引入预订/政策页等无关路由。**

---

## 合并顺序与依赖图

```
Unit 1 (DB) ─────────────────────────────────────────────┐
     │                                                     │
     ├── Unit 4 (Memory) ──────────┐                       │
     │                              │                       │
Unit 2 (Shared Utils) ──┬── Unit 3 (Query Understanding)  │
                        │                                  │
                        ├── Unit 6 (Retrieval) ── Unit 7 (Guided Search)
                        │                                  │
                        ├── Unit 9 (CompareAgent)          │
                        │                                  │
Unit 5 (Context) ───────┤                                  │
                        │                                  │
Unit 12 (PropertyService)                                 │
                        │                                  │
Unit 13 (EmbeddingService)                                │
                        │                                  │
                        ├── Unit 8 (SearchAgent) ──────────┤
                        │                                  │
                        └── Unit 10 (Dispatcher) ──────────┘
                                        │
                                  Unit 11 (API+Schema)
                                        │
                                  Unit 14 (CompareService)
                                        │
                          ┌─────────────┴─────────────┐
                          │  前端层                    │
                          │                            │
                    Unit 15 (Types)                    │
                          │                            │
                    Unit 16 (Utils)                    │
                          │                            │
                    Unit 17 (Services)                 │
                          │                            │
                    Unit 18 (Store)                    │
                          │                            │
                    Unit 19 (Components)               │
                          │                            │
                    Unit 20 (Views)                    │
                          └────────────────────────────┘
```

---

## 合并批次与预估

| 批次 | Unit | 操作类型 | 主要风险 | 预计 |
|------|------|---------|---------|------|
| **第 1 批** | 1, 2, 12, 13 | 新增 + 手动合并 + 删 legacy | 迁移执行、search_unit_types 改库存聚合 | 3-4h |
| **第 2 批** | 3, 5, 6, 7 | 全部新增，直接复制 | 无（全新文件） | 1h |
| **第 3 批** | 4 | 全部新增，直接复制 | 依赖 Unit 1 的表和 Unit 2 的工具 | 0.5h |
| **第 4 批** | 8, 9, 10 | 覆盖 + 删 legacy + 改引用 | SearchAgent 删 5 块旧代码后管线是否完整 | 4-6h |
| **第 5 批** | 11, 14 | 覆盖 + 确认 HEAD 独有端点 | API 向后兼容性 | 2h |
| **第 6 批** | 15, 16, 17 | 追加 + 新增 | TypeScript 编译 | 1-2h |
| **第 7 批** | 18, 19 | 追加 + 新增 | Store 方法签名兼容 | 1-2h |
| **第 8 批** | 20 | 手动合并 + 覆盖 | Search.vue 冲突最重，需精细逐块操作 | 3-5h |

---

## HEAD 特定冲突速查表

| PR #43 假设 | HEAD 现实 | 解决方式 |
|------------|----------|---------|
| `Room` 模型存在（`__tablename__="properties"`） | `Room=UnitType`（别名），无 `properties` 表 | 删除所有 `_legacy_*` 代码；Compare/Dispatcher 中的 Room 引用改 UnitType |
| `properties` 表有 embedding 列 | 无此表 | `20260725_0100` 迁移只做 `unit_types` |
| `agent_search_candidates.property_id` FK→`properties` | 无此表 | FK 改为→`unit_types` |
| `search_unit_types()` 中 `LEFT JOIN rooms` 聚合库存 | 无 `rooms` 表 | `available_rooms` 固定为 1，取 UnitType.status |
| `property_amenities()` 三层合并 | Property=UnitType | 改为两层合并（UnitType + Institute） |
| `RoomCommute.room_id` FK→`properties` | HEAD 可能已改 | 确认 HEAD 表结构，必要时改为直接关联 unit_type_id |
| Dispatcher 引用 `filter_agent` | HEAD 有 | 确认模块路径一致 |
| `chat_messages.metadata_` JSONB 列 | HEAD 可能无 | Unit 1 迁移补上 |
| `NotificationChannel/DeliveryStatus` 等模型 | HEAD 已删除 | `models/__init__.py` 合并时不引入 |
| 旧 ReAct 路径（`search_react`, `run_react_loop`） | HEAD 有 | 全部用 PR #43 的确定性管线替换 |

---

## 不应合并的内容

以下文件属于 PR #43 工作区的无关改动，**全部跳过**：

```
frontend/src/views/Home.vue                  ← 首页 API 导入补充
frontend/src/router/index.ts                 ← 预订路由 + 政策页（只取 Agent 路由）
frontend/src/services/profile.ts             ← 个人中心统计（新增）
frontend/src/utils/orderPresentation.ts      ← 订单工具（新增）
frontend/src/utils/paymentResult.ts          ← 支付工具（新增）
frontend/src/utils/profileSelection.ts       ← 个人中心工具（新增）
frontend/src/utils/profileSummary.ts         ← 个人中心工具（新增）
frontend/src/views/policies/                 ← 政策页面（新增）
backend/test/TEST_GUIDED_SEARCH.html         ← 手动测试页
backend/scripts/seed_agent_demo.py           ← 演示数据（非运行时必须，但建议保留做开发数据）
backend/package.json                         ← PR #43 无意引入
```

# 搜索页三栏 Agent 集成与合并指南

> 编写日期：2026-08-03
> 当前开发分支：`feat/agent-search-compare-update`
> 面向对象：仓库维护者、前端 Reviewer、后端 Reviewer、数据库维护者
> 关联背景文档：`docs/agent-interaction-rag-upgrade-report.md`

## 1. 文档目的

本次改动把普通房源搜索页从“两栏”升级为可选的“三栏”工作区：

```text
左侧筛选条件 | 中间房源搜索结果 | 右侧 AI 租房管家
```

用户可以先使用普通筛选，再让 Agent 在现有条件上继续细化；也可以直接向 Agent 描述需求，由 Agent 把明确的结构化条件同步到左侧筛选栏，并把推荐结果同时显示在中间结果区和右侧对话区。

本文重点说明：

1. 页面和交互具体如何修改。
2. 前后端新增了什么数据合同。
3. 数据库是否需要迁移。
4. 哪些文件属于本功能，哪些是必须一起合并的依赖。
5. 当前工作区中哪些改动与本功能无关，不应顺带合并。
6. 如何 Review、部署、验收和回滚。

## 2. 功能范围

### 2.1 已实现

- 搜索页右上角增加 `Agent` 按钮。
- 已登录用户点击按钮后，右侧打开 AI 租房管家。
- 未登录用户点击后提示登录，并携带当前搜索页作为登录后的返回地址。
- 桌面宽屏显示左、中、右三栏，不要求用户手动拖动页面宽度。
- 较窄屏幕改为右侧覆盖抽屉，避免把房源卡片压得过窄。
- Agent 组件按首次打开时懒加载，搜索页首屏不会提前加载对话面板代码。
- 搜索页当前条件通过 `context_filters` 传给 Agent。
- Agent 返回的明确条件通过 `filter_patch` 回填左侧筛选栏。
- Agent 返回的房源同时显示为右侧对话卡片和中间搜索结果。
- Agent 推荐卡点击后跳转到正确的 `/property/:id` 详情页。
- 地图模式下打开、关闭 Agent 或替换推荐结果后，重新计算地图尺寸和标记。
- 关闭右侧面板后，对话消息和会话 ID 仍保存在现有 Pinia `agentChat` store 中；同一次前端运行期间重新打开不会创建全新会话。

### 2.2 当前未实现

- 中间房源卡片没有新增“勾选多套房源”控件。
- 搜索页没有把当前结果的房源 ID 列表传给 Agent。
- 因此，“请对比我刚才在中间选中的这三套”尚不是本次三栏功能的完整能力。
- 右侧面板当前使用普通非流式请求；完整 SmartRent 页面已有 SSE，但尚未复用到该面板。
- 没有实现可拖拽分隔条，三栏宽度按响应式规则固定。

## 3. 用户流程

### 3.1 先筛选，再询问 Agent

1. 用户在左侧设置区域、预算、户型、入住时间等条件。
2. 中间区域先展示普通搜索结果。
3. 用户打开右侧 Agent，当前左侧条件会显示为上下文 chips。
4. 用户继续提问，例如：“预算改成 2500 以内，最好离地铁近一点。”
5. 前端把当前筛选作为 `context_filters`，把本轮文字作为 `message` 发送。
6. 后端将“2500 以内”识别为明确条件并返回 `filter_patch.price_max=2500`。
7. “最好离地铁近一点”作为软偏好参与 Agent 检索，但不会强制写入普通筛选栏。
8. 推荐房源同时进入右侧对话卡片和中间结果区。

### 3.2 直接询问 Agent

1. 用户不必先手动填写筛选条件，直接打开 Agent。
2. 用户输入：“想住苏州工业园区，预算 3000 以内，一室。”
3. 后端从自然语言提取明确条件。
4. 响应中的 `filter_patch` 同步更新左侧区域、最高预算和卧室数。
5. 响应中的 `recommendations` 同时更新中间房源结果和右侧推荐卡片。
6. 后续用户可以继续说“再便宜一点”或“不要独卫了”，会话状态负责承接上一轮条件。

### 3.3 防止结果互相覆盖

Agent 有推荐结果时，页面先应用 `filter_patch`，但不立即触发一次普通搜索，然后直接把 Agent 的推荐写入中间结果区。这样可以避免普通搜索响应覆盖 Agent 已排序的结果。

Agent 没有返回推荐结果时，页面在应用 `filter_patch` 后触发普通搜索，保证左侧条件变化仍然能刷新中间内容。

## 4. 页面布局与性能策略

### 4.1 响应式布局

| 视口宽度 | Agent 展示方式 | 宽度 |
|---|---|---:|
| `> 1360px` | 三栏并排 | `390px` |
| `1101px - 1360px` | 三栏并排 | `350px` |
| `<= 1100px` | 右侧固定覆盖抽屉 + 遮罩 | `min(400px, 100vw)` |
| `<= 900px` | 主搜索区单列，Agent 仍为覆盖抽屉 | 最大为整个视口宽度 |

当前没有手动拖拽缩放。固定断点的优点是布局稳定、实现和测试成本较低；后续如果真实用户确实有对比宽度需求，再单独增加可拖拽分隔条和宽度持久化。

### 4.2 首次打开是否会卡顿

本次使用 `defineAsyncComponent` 懒加载 `SearchAgentPanel.vue`：

- 未打开 Agent 时，不加载右侧面板组件代码。
- 第一次打开时才下载组件 chunk 并调用 `ensureSession()`。
- 加载期间展示固定高度的加载状态，避免布局跳动。
- 发送消息时展示“正在搜索和整理房源”，HTTP 超时设置为 60 秒。

这能降低普通搜索页首屏成本，但不能消除 LLM 和房源检索本身的后端延迟。后续性能优化优先级建议：

1. 将右侧面板切换到现有 `sendMessageStream()` SSE 能力，先显示增量文本。
2. 记录面板首次打开耗时、会话创建耗时和消息首字节耗时。
3. 如果 Agent 使用率较高，可在浏览器空闲时预取组件 chunk，但不要提前创建会话。

## 5. 前端实现

### 5.1 `frontend/src/views/Search.vue`

主要职责：

- 在结果区右上角增加 Agent 开关。
- 使用 `defineAsyncComponent` 懒加载右侧面板。
- 管理 `agentOpen`、`fromAgent` 和 Agent 推荐结果状态。
- 把左侧搜索状态转换为 Agent 可识别的 `AgentFilters`。
- 接收右侧面板的 `apply-filter-patch` 事件并更新左侧控件。
- 接收 `show-recommendations` 事件并更新 Pinia 房源搜索结果。
- 响应三栏布局变化并调用地图 `invalidateSize()`。
- 修正房源详情路由为 `/property/:id`。

### 5.2 `frontend/src/components/search/SearchAgentPanel.vue`

新增的搜索页专用面板，主要职责：

- 复用 `agentChat` store 创建或恢复 Agent 会话。
- 展示当前搜索条件 chips、对话消息、推荐卡片和快捷选项。
- 将当前筛选作为 `context_filters` 随每条消息发送。
- 将后端 `filter_patch` 通过事件交给 `Search.vue`，组件本身不直接修改搜索页状态。
- 将全部推荐通过事件交给 `Search.vue` 更新中间结果。
- 对话中最多直接展示 3 张推荐卡，但“在搜索区显示”使用完整推荐数组。
- 推荐详情跳转到 `/property/:id`。

### 5.3 `frontend/src/services/agent.ts`

复用现有 Agent API 服务，在普通消息请求中增加：

```ts
context_filters: body.context_filters
```

右侧面板当前调用：

```text
POST /api/v1/agent/sessions/{session_id}/messages
```

请求超时为 60 秒。文件中已有 SSE 方法，但本面板暂未使用。

### 5.4 `frontend/src/types/agent.ts`

前端合同增加：

- `AgentMessageRequest.context_filters`
- `AgentMessageResponse.filter_patch`
- 推荐排名、总分、分项分和来源元数据
- 查询改写、会话状态、来源、约束放宽轨迹和指代解析类型

## 6. 后端 API 与条件合并

### 6.1 请求示例

```json
{
  "message": "预算改成2500以内",
  "context_filters": {
    "district": "苏州工业园区",
    "price_max": 3000
  }
}
```

`context_filters` 表示普通搜索页当前条件，它是对话上下文，不等同于本轮用户新输入，也不等同于强制覆盖值。

保留的 `filters` 字段仍表示调用方显式传入的最终强制条件。当前搜索页右侧面板只发送 `context_filters`，不发送 `filters`。

### 6.2 响应示例

```json
{
  "reply": "已把预算调整到 2500 以内，并找到以下房源。",
  "intent": "recommend",
  "recommendations": [],
  "filter_patch": {
    "price_max": 2500
  }
}
```

`filter_patch` 只描述本轮适合安全同步到普通筛选栏的变化，不是完整会话状态快照。

### 6.3 合并优先级

当前有效条件的优先级从低到高为：

```text
长期用户偏好
< 当前会话状态
< 搜索页 context_filters
< 本轮自然语言提取结果
< filters 显式强制条件
```

列表条件默认增量合并。只有用户明确说“取消”“不要”时才删除对应字段或列表值。

### 6.4 `filter_patch` 规则

- 明确、可结构化的条件允许回填。
- “最好”“尽量”“优先”等软偏好不回填普通筛选栏。
- 同一字段被明确标记为硬条件时，即使同时出现在软偏好元数据中，也按硬条件回填。
- 用户取消某个条件时返回该字段为 `null`。
- 用户明确要求重置时，所有可同步搜索字段返回 `null`。
- 后端只返回白名单字段，避免任意对象修改前端状态。

后端可同步字段白名单：

```text
district
price_min
price_max
bedrooms
property_type
amenities
room_type
min_lease_months
max_lease_months
available_from
institution
commute_minutes
```

### 6.5 前端字段映射

| Agent 字段 | 搜索页目标 | 处理方式 |
|---|---|---|
| `district` | `filters.district` | 切换到城市模式并清除学校模式 |
| `price_min` | `filters.price_min` | 转为有限数字，`null` 清除 |
| `price_max` | `filters.price_max` | 转为有限数字，`null` 清除 |
| `bedrooms` | `filters.bedrooms` | 转为数字 |
| `property_type` | `filters.property_type` | 使用现有房型枚举 |
| `room_type` | `filters.room_type` | 字符串写入；独卫设施也会映射为 `ensuite` |
| `amenities` | features / amenities / location_tags | 通过白名单把中文设施名称映射到现有三个控件组，未知值忽略 |
| `available_from` | `filters.move_in_month` | 日期提取为 `YYYYMM` |
| `institution` | 学校搜索模式 | 当前仅映射 UCLA、NUS、NTU 三组别名 |
| `commute_minutes` | `commuteTime` | 仅在学校模式下映射到 5/10/15/20/30 分钟档位 |
| `min_lease_months` / `max_lease_months` | `durationFilter` | 粗粒度映射为短租、中租、长租 |

## 7. 后端实现改动

### 7.1 `backend/app/schemas/agent.py`

- `AgentMessageRequest` 增加 `context_filters`。
- `AgentMessageResponse` 增加 `filter_patch`。
- 扩展推荐分数、来源、状态、查询改写和指代解析等合同。
- 列表和字典默认值改用 `default_factory` 的新增部分，避免共享可变默认值。

### 7.2 `backend/app/api/v1/routes/agent.py`

- 普通消息和 SSE 消息都解析并透传 `context_filters`。
- 普通响应序列化 `filter_patch`。
- 扩展推荐结果的排名、分数和来源字段。
- 对 UnitType 推荐使用真实可租 `property_id` 覆盖展示 ID，确保详情页可打开。
- 不再由前端或路由根据价格、户型猜测设施，只透传真实数据。

### 7.3 `backend/app/services/agentic/dispatcher.py`

- Dispatcher 接收 `context_filters`。
- 查询理解时将会话条件和搜索页条件作为上一轮上下文。
- 通过 `_build_filter_patch()` 生成本轮可回填字段。
- 重置、删除、硬条件和软偏好按统一规则处理。
- 普通响应和 SSE 最终元数据都包含 `filter_patch`。

### 7.4 `backend/app/services/agentic/memory.py`

- 合并搜索页上下文、会话状态、长期偏好、本轮提取和显式筛选。
- 保持列表条件的增量语义。
- 持久化当前会话筛选状态、上轮候选和搜索审计数据。

## 8. 数据库影响

### 8.1 结论

如果只看“三栏布局、按钮、条件回填和结果展示”，它本身不需要新增业务表或修改房源表字段。

但是，当前分支中的 Dispatcher 已经接入 Agent Memory/RAG 主链路，三栏功能调用的就是这条主链路。因此按当前实现合并时，必须同时合并对应模型和迁移，不能只挑选前端文件后直接上线。

### 8.2 新增表

迁移新增 4 张 Agent 专用表，没有修改现有业务表的列：

| 表名 | 用途 | 关键数据 |
|---|---|---|
| `agent_session_states` | 会话短期状态 | 条件、指代映射、上轮结果、滚动摘要 |
| `agent_user_memories` | 用户跨会话偏好 | 偏好 JSON、用户画像摘要 |
| `agent_search_runs` | 每次搜索审计 | 原始问题、改写问题、有效条件、放宽轨迹、耗时 |
| `agent_search_candidates` | 候选审计 | 房源 ID、户型 ID、名次、分数、来源元数据 |

迁移文件：

```text
backend/alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py
```

迁移关系：

```text
down_revision: 20260725_0100
current head: 20260802_0101
```

部署命令：

```bash
cd backend
alembic upgrade head
```

回滚该迁移会删除上述 4 张 Agent 表，不修改已有房源、用户、订单等业务表。

### 8.3 数据与隐私 Review

`agent_search_runs.original_query` 会保存用户搜索原文。上线前需要由仓库维护者确认：

- 是否允许持久化搜索原文。
- 数据保留周期和清理任务。
- 用户删除账号时是否级联清理或另行清理。
- 日志、数据库备份和分析平台对这类文本的访问权限。

当前外键对用户和会话使用级联删除，但仍建议按产品隐私政策做一次确认。

## 9. 文件级合并清单

### 9.1 本次三栏功能直接改动

| 文件 | 类型 | 说明 |
|---|---|---|
| `frontend/src/views/Search.vue` | 修改 | Agent 入口、三栏布局、筛选回填、推荐结果同步、地图尺寸处理 |
| `frontend/src/components/search/SearchAgentPanel.vue` | 新增 | 搜索页右侧 Agent 对话面板 |
| `frontend/src/services/agent.ts` | 修改 | 普通请求透传 `context_filters` |
| `frontend/src/types/agent.ts` | 修改 | 请求、响应、推荐及 Agent 状态类型 |
| `backend/app/schemas/agent.py` | 修改 | `context_filters`、`filter_patch` 及扩展响应合同 |
| `backend/app/api/v1/routes/agent.py` | 修改 | 请求透传、响应序列化、真实房源 ID 映射 |
| `backend/app/services/agentic/dispatcher.py` | 修改 | 条件合并、回填 patch、主链路接入 |
| `backend/app/services/agentic/memory.py` | 新增 | 搜索页上下文与会话状态合并 |
| `backend/tests/test_agent_filter_patch.py` | 新增 | 回填、软偏好、取消和重置规则测试 |

### 9.2 当前实现必须一起合并的 Agent 主链路依赖

由于 `dispatcher.py` 已整体升级，以下内容不能遗漏：

| 文件 | 作用 |
|---|---|
| `backend/app/models/agent_intelligence.py` | 4 张 Agent 表的 ORM 模型 |
| `backend/app/models/__init__.py` | 注册新增模型 |
| `backend/alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py` | 数据库迁移 |
| `backend/app/services/agentic/context.py` | 历史和候选上下文打包 |
| `backend/app/services/agentic/query_understanding.py` | 条件提取、删除语义和查询改写 |
| `backend/app/services/agentic/retrieval.py` | 混合召回、约束放宽和重排 |
| `backend/app/services/agentic/agents/search_agent.py` | 新检索和 Grounded Answer 接入 |
| `backend/app/services/property_service.py` | 可租库存和真实 property ID 查询支持 |
| `backend/app/core/config.py` | Agent Memory/RAG 配置 |
| `backend/.env.example` | 新配置示例 |
| `backend/tests/test_agent_intelligence.py` | Agent 主链路纯规则测试 |
| `frontend/src/views/SmartRentView.vue` | 与扩展 Agent 合同配套的现有完整 Agent 页面 |

`backend/scripts/seed_agent_demo.py` 是演示数据脚本，不是运行时必须项，可由维护者决定是否随功能合并。

Agent 主链路的详细设计和配置说明见：

```text
docs/agent-interaction-rag-upgrade-report.md
```

### 9.3 不应按当前工作区状态顺带合并的内容

当前工作区存在其他功能的未提交修改。以下文件或目录与三栏搜索 Agent 没有直接依赖，应拆分到其他 PR 或由其负责人确认：

```text
frontend/src/views/Home.vue
frontend/src/router/index.ts
frontend/src/services/profile.ts
frontend/src/utils/orderPresentation.ts
frontend/src/utils/paymentResult.ts
frontend/src/utils/profileSelection.ts
frontend/src/utils/profileSummary.ts
frontend/src/views/policies/
backend/test/TEST_GUIDED_SEARCH.html
```

维护者不应直接执行“提交当前全部工作区改动”来形成该功能 PR。建议按上面的文件清单分组暂存，并在暂存后再次检查 diff。

## 10. 推荐合并顺序

1. 先把本功能文件从混合工作区隔离到独立功能分支或独立提交。
2. 合并 Agent 模型、Alembic 迁移、配置和 Memory/RAG 主链路。
3. 合并后端 schema、route、dispatcher 和对应测试。
4. 合并前端 `agent.ts` 与 `types/agent.ts` 合同。
5. 合并 `SearchAgentPanel.vue` 和 `Search.vue` 页面集成。
6. 执行数据库迁移和后端测试。
7. 启动前后端，按第 13 节完成桌面、窄屏、列表和地图人工验收。

建议拆成以下提交，方便 Review 和必要时回滚：

```text
feat(db): 新增 Agent 会话记忆与搜索追踪表
feat(backend): 支持搜索页条件上下文与筛选回填
feat(frontend): 在房源搜索页接入右侧 Agent 面板
test(search): 补充 Agent 筛选回填规则测试
docs(search): 补充三栏 Agent 合并指南
```

## 11. Review 与冲突热点

### 11.1 高冲突文件

- `frontend/src/views/Search.vue`：页面体积较大，包含筛选、地图、分页和新 Agent 布局，建议按功能块 Review，不要整文件覆盖。
- `backend/app/services/agentic/dispatcher.py`：本分支是主链路级重写，不适合只手工复制 `_build_filter_patch()`。
- `backend/app/schemas/agent.py` 与 `frontend/src/types/agent.ts`：必须保持字段名称、可空性和默认值一致。
- `backend/app/api/v1/routes/agent.py`：同时包含推荐实体 ID 修正和扩展响应序列化。
- `backend/app/services/property_service.py`：影响 Agent 候选检索范围，需后端重点 Review 查询性能和可租库存语义。

### 11.2 Reviewer 应重点确认

- `context_filters` 不会覆盖本轮自然语言的新条件。
- 软偏好不会错误地写入普通筛选栏。
- `null` 清除能正确同步左侧控件。
- Agent 推荐使用真实 `property_id`，详情页、地图和后续候选操作指向同一实体。
- 有 Agent 推荐时，普通搜索不会随后覆盖推荐顺序。
- 未知设施名称不会写入错误筛选组。
- 学校 ID 不应长期依赖硬编码；当前 UCLA/NUS/NTU 映射需要和目标环境基础数据 ID 核对。
- `agent_search_runs.original_query` 的留存符合隐私要求。
- 新表索引和 JSONB 数据量符合预期，后续有清理策略。

## 12. 自动验证结果

已执行以下 Agent 相关测试：

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest --noconftest -q \
  tests/test_agent_filter_patch.py \
  tests/test_agent_intelligence.py
```

结果：

```text
15 passed, 1 warning in 0.46s
```

其他已确认项：

- 标准库测试共 10 项通过。
- Python `compileall` 通过。
- `git diff --check` 通过。
- Alembic 只有一个 head：`20260802_0101`。
- 本次涉及的前端文件没有出现在 `vue-tsc` 错误列表中。

当前不能声称完整仓库测试全部通过：

- 常规 pytest 会在现有 `tests/conftest.py` 导入阶段被缺失的 `app.services.booking_availability_service` 阻断，因此 Agent 纯规则测试使用了 `--noconftest`。
- 完整 `npm run build` 仍被工作区已有错误阻断，主要包括 booking 模块缺少文件/类型、缺少 `vitest` 和 `@vue/test-utils`、PropertyCard/RentalRulesCard 等历史类型错误。

这些问题当前没有指向本次三栏文件，但合并前维护者应在目标分支重新跑一次完整 CI，避免目标分支基线不同。

## 13. 人工验收步骤

### 13.1 基础布局

- [ ] 打开 `/search`，默认仍为左侧筛选 + 中间结果两栏。
- [ ] 右上角能看到 Agent 按钮。
- [ ] 未登录点击 Agent 会跳到登录页，登录返回地址是当前搜索页。
- [ ] 已登录点击后，宽屏显示三栏，页面没有横向溢出或文字重叠。
- [ ] 视口缩小到 1100px 以下时，Agent 变为右侧抽屉并显示遮罩。
- [ ] 点击关闭按钮或遮罩能关闭面板。
- [ ] 关闭再打开后，本次会话消息仍在。

### 13.2 筛选同步

- [ ] 左侧先设区域和预算，打开 Agent 后能看到对应上下文 chips。
- [ ] 输入“预算改成 2500 以内”，左侧最高预算更新为 2500。
- [ ] 输入“不要预算限制了”，预算字段被清除。
- [ ] 输入“重新开始”，可同步字段全部清除。
- [ ] 输入“最好便宜一点”，软偏好参与回复但不强制改写左侧预算。
- [ ] 输入明确区域后，学校模式和城市模式切换符合预期。
- [ ] 分别验证 UCLA、NUS、NTU 的学校别名映射；在目标数据库核对 ID。

### 13.3 推荐结果

- [ ] Agent 有推荐时，右侧显示最多 3 张卡片。
- [ ] 中间区域显示 Agent 返回的完整推荐列表。
- [ ] 推荐顺序没有被随后发起的普通搜索覆盖。
- [ ] 点击右侧卡片能打开 `/property/{property_id}`。
- [ ] 图片、价格币种、区域和匹配原因显示正常。
- [ ] 返回空推荐时，左侧条件仍更新并触发普通搜索。

### 13.4 地图与响应式

- [ ] 切到地图模式后打开和关闭 Agent，地图没有灰块或尺寸错误。
- [ ] Agent 推荐写入后，地图标记与中间结果一致。
- [ ] 在 1440px、1280px、1024px 和移动端宽度分别检查布局。
- [ ] 输入框、发送按钮、推荐卡标题和价格没有溢出或重叠。

### 13.5 后端和数据库

- [ ] `alembic upgrade head` 成功。
- [ ] 4 张新表创建成功，现有业务表结构未变化。
- [ ] 消息端点同时接受旧请求和带 `context_filters` 的新请求。
- [ ] `filter_patch` 只返回白名单字段。
- [ ] 搜索 Run 和候选审计正常写入，失败请求不会留下错误的半完成状态。

## 14. 已知限制与后续建议

### 14.1 当前结果不是“用户选中的一批房子”

搜索页传给 Agent 的是筛选条件，不是中间结果 ID，也没有显式多选状态。若产品要支持“先手选三套，再让 Agent 对比”，建议后续增加：

1. 房源卡多选控件和已选数量状态。
2. 将选中 ID 通过现有 `compare_property_ids` 发送。
3. 在右侧显示已选候选清单，并支持移除和清空。
4. 对下架或无权限房源在后端重新校验，不能只信任前端 ID。

### 14.2 学校映射需要服务端数据化

当前前端只映射 UCLA、NUS、NTU，并假设 ID 分别为 1、2、3。这个实现适合现有演示数据，但不适合多环境长期维护。建议改为根据后端学校列表或稳定 slug 映射，不应依赖数据库自增 ID。

### 14.3 右侧面板建议流式化

非流式请求最长等待 60 秒，虽然有加载态，但用户不能提前看到内容。建议后续复用 `sendMessageStream()`：

- token 到达后更新同一个助手气泡。
- 最终 meta 到达后再同步 `filter_patch` 和推荐结果。
- 面板关闭时使用 `AbortController` 取消未完成请求。
- 防止流式结果重复应用筛选或推荐。

### 14.4 条件映射不是完全无损

普通筛选栏与 Agent 条件模型不是一一对应：租期和通勤使用档位，设施使用本地白名单，学校仅支持少量别名。新增 Agent 字段时，应同时更新：

1. 后端 `_SEARCH_PAGE_FILTER_FIELDS`。
2. 前端 `AgentFilters` 类型。
3. `Search.vue` 的 `applyAgentFilterPatch()`。
4. 请求侧 `agentFilters` 映射。
5. `test_agent_filter_patch.py` 和前端交互测试。

## 15. 回滚方案

### 15.1 仅关闭搜索页入口

如果上线后只有三栏交互出现问题，可以先回滚 `Search.vue` 和 `SearchAgentPanel.vue` 的入口集成。扩展后的 Agent API 字段均有默认值，现有完整 Agent 页面可以继续运行。

### 15.2 回滚后端主链路

若需要回滚 Dispatcher/Memory/RAG，不应只回滚 `dispatcher.py`。需要同步回滚 schema、route、service、types 和相关配置，保证前后端合同一致。

### 15.3 回滚数据库

确认没有线上功能继续依赖新表后，回退到上一迁移：

```bash
cd backend
alembic downgrade 20260725_0100
```

该操作会删除 4 张 Agent 专用表及其中的会话记忆和搜索审计数据。执行前应确认是否需要备份，且不要在仍运行新 Dispatcher 的实例上先降级数据库。

## 16. 最终 Merge Checklist

- [ ] PR 只包含本功能和明确列出的 Agent 主链路依赖。
- [ ] 无关 Home、Profile、Policy、Booking 修改已移出本 PR。
- [ ] 前后端 `context_filters` 和 `filter_patch` 合同一致。
- [ ] 数据库迁移只有一个 head，目标环境已执行升级。
- [ ] Agent 相关自动测试通过。
- [ ] 目标分支完整 CI 通过，或已有基线失败被单独记录。
- [ ] 完成四种视口和地图模式人工验收。
- [ ] 核对学校基础数据 ID，或在合并前改为稳定标识映射。
- [ ] 确认搜索原文的隐私和保留策略。
- [ ] PR 描述关联对应 Issue，并按仓库规范包含 `Closes #X`。

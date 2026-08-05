# 近期修改汇总（2026-07-27—2026-08-04）

> 文档日期：2026-08-04
> 当前分支：`feat/agent-search-compare-update`
> 对比基线：`main` / `origin/main` 的 `2e48d05`
> 当前提交：`3f0bee1`
> 说明：本文把已经提交的内容和仍在本地工作区的内容分开记录，避免把“代码已写”误写成“已经提交、迁移或上线”。

## 1. 总体结论

这段时间的工作不只是增加缓存，而是围绕租房 Agent 完成了一次较大范围的搜索、对比、记忆和交互升级：

1. 语义搜索从应用层计算调整为 PostgreSQL pgvector/HNSW 检索。
2. Agent 回复接入真正的 SSE token 流式输出和完整推荐卡。
3. 综合对比从多轮 ReAct 工具循环改为“批量取数 + 确定性评分 + 单次 LLM 解释”。
4. 新增 Query Rewrite、混合召回、约束消融、七信号重排和 Grounded Answer。
5. 新增会话短期状态、账号级长期偏好、搜索轨迹和候选评分审计。
6. AI 找房页增加历史会话、长期记忆、FAQ、固定入口和横向推荐卡。
7. 普通搜索页增加国家/地区筛选和右侧 Agent，并能比较用户当前看到的全部房源。
8. 修复 Property、UnitType、Institute 三层数据中的 ID、国家、设施和币种映射问题。

当前状态分为两部分：

| 状态 | 范围 | 规模 |
|---|---|---:|
| 已提交并已推送到当前远端分支 | 2026-07-27 至 2026-07-29 的 5 个提交 | 30 个文件，`+1663/-570` |
| 本地工作区待提交 | 2026-08-02 至 2026-08-04 的记忆、检索、页面联动及兼容修复 | 38 个已跟踪文件，约 `+4218/-1080`，另有未跟踪文件 |

## 2. 已提交修改时间线

### 2.1 2026-07-27：Agent 搜索与对比基础升级

提交：`2d57d96 feat(backend+frontend): agent 搜索与对比模块更新`

主要修改：

- 将 `properties`、`unit_types` 的 Embedding 恢复为 `vector(1536)`。
- 新增 cosine HNSW 索引，语义排序下推 PostgreSQL。
- 搜索不再拉取最多 500 条向量到应用层逐条计算，候选规模收敛到约 60 条。
- 房源搜索和聊天 RAG 的距离计算从 L2 调整为 cosine，与索引保持一致。
- Embedding 服务改为进程级单例，复用 HTTP 和 Redis 连接。
- 接入已有的 Redis 文本向量缓存，TTL 为 1 小时。
- 查询向量生成与条件提取并行执行。
- 新增数据库连接池大小、溢出连接、等待超时、连接探活和连接回收配置。
- 新增 POI 偏好注册、POI 距离软排序和渐进筛选选项。
- 前端对比请求开始支持传递 POI 偏好。

主要文件：

- `backend/alembic/versions/20260725_0100_embedding_vector_hnsw.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/property_service.py`
- `backend/app/services/agentic/agents/search_agent.py`
- `backend/app/services/agentic/guided_search.py`
- `backend/app/services/compare_scoring.py`
- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `frontend/src/services/agent.ts`

### 2.2 2026-07-29：修复合并后的后端启动问题

提交：`4bd4a36 fix(backend): 修复 main 合并损坏——模型导入/Property映射/路由挂载`

主要修改：

- 清理不存在的通知模型导入。
- 将 Booking、Contract、RoomType 中无法解析的 `Property` 关系改为实际 ORM 模型 `Room`。
- 注册此前未挂载的 `/compare/sessions` 对比路由。
- 因此前合并缺失依赖，临时停用 bookings、contracts、payments 三组路由以保证应用启动。

注意：停用业务路由属于临时兼容处理，合并或发布前需要再次确认这些 API 是否已经恢复。

### 2.3 2026-07-29：渐进选房、真流式与推荐卡片

提交：`6f00d3b feat(agent): 渐进选房前端接通 + AI回复真流式 + 短提示词 + 推荐卡片`

主要修改：

- 将 SearchAgent 拆为确定性检索管线、非流式生成和流式生成。
- 把“完整生成后模拟打字”改为 LLM token 真流式。
- SSE 最终事件统一返回推荐卡、Top Picks、引导选项和其他元数据。
- 补全 UnitType 图片、设施、最短租期、优惠和 POI 距离映射。
- 首轮推荐直接附带真实 POI 距离。
- 新增 `GuidedOption`、`poi_distances` 等前后端契约。
- 新增 AI 推荐专用卡片 `RecPropertyCard.vue`。
- AI 找房页接入渐进筛选 chips、对比勾选、候选清单和详情入口。
- 正式挂载前端 `/compare` 路由。

### 2.4 2026-07-29：综合对比性能重写

提交：`5ec57a4 perf(compare): 综合对比 ReAct 循环重写为单次 LLM 调用`

旧流程需要 5—10 次串行 LLM 工具往返，并依赖已经丢失的 `run_react_loop`。新流程改为：

```text
批量预加载房源/POI/评价/安全数据
→ 确定性评分
→ 单次 LLM 解释
→ LLM 失败时规则摘要兜底
```

这次修改重写了执行方式，但保留原有评分公式、雷达图分数和前端响应结构；`tool_trail` 为兼容旧契约保留，但固定为空。

主要文件：`backend/app/services/comparison_service.py`。

### 2.5 2026-07-29：恢复口语化长回复提示词

提交：`3f0bee1 revert(agent): 推荐提示词恢复 3b426e0 口语化长文版`

主要修改：

- 推荐回复从 120—200 字恢复为约 450—750 字。
- 恢复“需求确认、逐套介绍、横向比较、总结建议”四段式结构。
- 流式和非流式回复的 `max_tokens` 恢复为 2000。
- 真流式、渐进筛选、推荐卡片和搜索管线拆分继续保留。

## 3. 当前工作区待提交修改

### 3.1 Agent 主链重构

当前 Dispatcher 主链已经调整为：

```text
恢复会话状态和账号偏好
→ 分类意图与阶段
→ Query Rewrite
→ 合并有效筛选条件
→ 混合召回
→ 约束消融
→ 多信号重排
→ Grounded Context 打包
→ SSE/普通响应
→ 原子保存消息、记忆和搜索轨迹
```

主要文件：

- `backend/app/services/agentic/dispatcher.py`
- `backend/app/services/agentic/agents/search_agent.py`
- `backend/app/services/agentic/query_understanding.py`
- `backend/app/services/agentic/retrieval.py`
- `backend/app/services/agentic/context.py`
- `backend/app/services/agentic/memory.py`

### 3.2 Query Rewrite 与条件合并

新增 `query_understanding.py`，一次结构化调用完成：

- 本轮新增或修改条件提取。
- 要删除的字段和列表值识别。
- 独立可检索表达改写。
- exact、relative、reference、exploratory 查询类型识别。
- 明确长期记忆字段识别。

模型不可用时使用确定性规则兜底，当前覆盖：

- NUS、NTU、UCLA、UCL、LSE、HKU 等学校缩写及对应国家。
- 绝对预算、预算上下浮动和“再便宜一点”等相对表达。
- studio、合租、卧室数、币种、通勤方式和通勤分钟数。
- 独卫、健身房、自习室、泳池等设施别名。
- “不要独卫、取消预算、不限区域”等删除语义。

筛选合并优先级固定为：

```text
账号长期偏好 < 当前会话状态 < 本轮自然语言理解 < 前端显式筛选
```

### 3.3 混合召回与确定性重排

搜索候选由两条召回腿组成：

1. 语义向量召回。
2. 结构化条件召回。

两路结果合并去重；Embedding 不可用时自动降级到结构化和词面匹配。严格结果不足时，只额外获取一次宽召回池，后续放宽试验均在内存中复用该候选池。

最终重排由七个确定性信号组成：

| 信号 | 权重 |
|---|---:|
| 语义相似度 | 32% |
| 词面匹配 | 12% |
| 预算贴合 | 18% |
| 通勤表现 | 14% |
| 周边 POI | 10% |
| 信息完整度 | 8% |
| 约束满足度 | 6% |

同分时按可租库存和价格稳定排序，并返回总分、分项分和稳定名次。

### 3.4 零结果约束消融与最小放宽

新增逐项约束试验：预算、区域、房型、卧室、面积、卫浴、设施、通勤、POI 距离和租期均可单独诊断。

规则如下：

- `hard_filters` 中的条件不自动放宽。
- 严格结果达到最低数量时不放宽。
- 严格结果为 1—2 套时保留真实结果，只返回可点击的放宽建议。
- 严格结果为 0 时最多自动应用一次最小放宽，并明确告诉前端放宽了什么。

### 3.5 Grounded Answer 与来源约束

新增候选上下文打包和事实边界：

- 最近历史默认最多保留 12 条、8,000 字符。
- 单条超长消息保留开头和结尾，旧内容用确定性状态摘要代替。
- 推荐阶段默认只给生成模型前 3 套事实；比较/决策阶段最多 5 套。
- 候选上下文默认最多 12,000 字符。
- 生成模型只能使用候选 `facts` 中的值。
- 字段为空或来源为 `missing` 时必须说明“暂无数据/建议确认”。
- 推荐 ID、名次和分数由后端确定，模型不能创造新房源或修改排名。
- 前端展示“房源基础信息、实时库存、通勤数据、周边设施、语义匹配”等来源标签。

### 3.6 会话短期状态、账号长期记忆和搜索审计

新增模型和迁移：

| 表/字段 | 用途 | 账号关联 |
|---|---|---|
| `chat_sessions.session_kind` | 区分普通客服会话与 Agent 会话 | 通过原会话关联 |
| `agent_session_states` | 会话阶段、筛选、引用映射、上轮结果和摘要 | `session_id + user_id` |
| `agent_user_memories` | 跨会话偏好、置信度和证据次数 | `user_id` 唯一 |
| `agent_search_runs` | 原查询、改写、有效条件、放宽轨迹、来源和耗时 | `session_id + user_id` |
| `agent_search_candidates` | 候选名次、总分、分项分和来源 | 通过 search run 间接关联 |

记忆规则：

- 国家、学校、房型等稳定字段首次明确表达时即可达到跨会话阈值。
- 预算等临时条件需要在不同会话重复出现，避免一次搜索永久污染画像。
- 同一会话重复表达不会重复累计证据。
- 用户主动点击保存时，偏好置信度直接设为 1。
- “重新开始”“从头开始”“清空条件”等重置表达目前会同时清空长期偏好，不只是重置当前会话条件。
- `AGENT_MEMORY_ENABLED=false` 只关闭主对话链中的长期偏好应用和自动学习；当前会话状态、指代映射和搜索审计仍会保存。

新增接口：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/v1/agent/sessions` | 当前账号的 Agent 会话列表 |
| `GET` | `/api/v1/agent/sessions/{id}/messages` | 回放历史消息及元数据 |
| `GET` | `/api/v1/agent/memory` | 读取长期偏好 |
| `PUT` | `/api/v1/agent/memory` | 保存或替换长期偏好 |
| `DELETE` | `/api/v1/agent/memory` | 清空长期偏好 |
| `POST` | `/api/v1/agent/sessions/{id}/messages` | 非流式消息，支持页面上下文和比较 ID |
| `POST` | `/api/v1/agent/sessions/{id}/messages/stream` | SSE 流式消息 |

主要文件：

- `backend/app/models/agent_intelligence.py`
- `backend/alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py`
- `backend/app/models/chat.py`
- `backend/app/services/chat_service.py`
- `backend/app/api/v1/routes/agent.py`
- `backend/app/schemas/agent.py`

### 3.7 指代解析和事实追问

每轮推荐后建立两类引用：

- 序号引用：第一套、第二套等。
- 语义引用：最便宜、通勤最近、面积最大、综合最好、刚才那套。

“这个有健身房吗”“这套附近有自习室吗”等问题会锁定上一轮具体房源，重新读取当前数据库字段，不再当成一次新的全局搜索。

设施回答只使用 Property、UnitType、Institute 的真实设施字段，并区分：

- 楼内/公寓自带设施。
- 楼外附近独立场所或 POI。

没有周边 POI 数据时会明确说明无法确认，不再把楼内设施冒充楼外附近设施。

### 3.8 对比功能补强

当前待提交代码进一步修改了 `CompareAgent`：

- 按传入顺序批量读取房源，减少逐条数据库查询。
- 预载 Property → UnitType → Institute 三层数据。
- 合并房间冗余设施、户型设施和公寓设施。
- 不同币种先换算为统一基准做评分，展示时仍使用房源原始币种。
- 新增 AUD 汇率、符号和文本识别。
- 规则降级摘要也使用真实币种，不再把海外房源统一显示为人民币。
- 搜索页“这几套哪个好”优先比较前端明确传入的当前结果 ID。
- 当前不足 2 套时，前端禁止发起虚假比较。

主要文件：

- `backend/app/services/agentic/agents/compare_agent.py`
- `backend/app/services/agentic/shared.py`
- `backend/app/services/currency.py`
- `frontend/src/components/search/SearchAgentPanel.vue`

## 4. 前端页面修改

### 4.1 AI 找房页 `frontend/src/views/AiSearch.vue`

- 左侧增加 Agent 历史会话、新对话和切换会话。
- 增加长期记忆展示、保存当前偏好和清空记忆。
- 固定显示欢迎说明、4 个 starter prompts 和 FAQ chips。
- 推荐卡放到回复正文上方，所有结果横向滚动展示。
- 支持勾选多套推荐进入精确比较。
- 输入升级为多行文本，前后端上限统一为 20,000 字。
- 使用公共 SSE 客户端逐 token 更新同一个助手气泡。
- 历史回放恢复推荐卡、状态 chips、来源和 FAQ 链接，不再只有纯文字。
- 小屏幕增加历史与记忆抽屉入口。
- `/ai-search` 增加登录保护。

### 4.2 搜索页 `frontend/src/views/Search.vue`

- 新增 SG、GB、US、HK、CN、AU 国家/地区筛选。
- 国家筛选同步 URL 和后端请求。
- 学校模式自动同步对应国家，避免 NUS 与旧国家条件冲突。
- 增加右侧 Agent 面板开关。
- 把当前筛选作为 `context_filters` 传给 Agent。
- 把当前可见结果作为比较 ID 传给 Agent；地图模式使用全部筛选结果。
- 接收 Agent 返回的筛选补丁和推荐结果。
- 统一海外房源币种格式，优先使用后端 `currency`，缺失时按国家推断。

### 4.3 搜索页 Agent `frontend/src/components/search/SearchAgentPanel.vue`

- 固定欢迎语、常用追问和 FAQ chips。
- 横向显示全部推荐卡，卡片位于正文上方。
- 支持 20,000 字输入和 SSE 流式回复。
- 比较当前搜索结果，不再默认退回购物车或无关旧候选。
- 当前结果少于 2 套时禁用比较并给出提示。

### 4.4 SmartRent 页面 `frontend/src/views/SmartRentView.vue`

- 显示当前“已记住”筛选 chips。
- 展示查询改写、来源、引导选项和流式状态。
- 推荐卡展示真实名次、匹配分、真实币种和数据库设施。
- 流中断时保留已生成文本并追加提示。
- 移除未实际落地的“多 Agent 深度”入口。

### 4.5 前端状态和 API 层

- `frontend/src/services/agent.ts`：新增会话、历史、记忆、SSE 接口。
- `frontend/src/stores/agentChat.ts`：管理多会话、历史回放和长期偏好状态。
- `frontend/src/types/agent.ts`：补充历史、来源、查询改写、状态摘要和流式元数据类型。
- `frontend/src/utils/currency.ts`：集中处理 CNY、GBP、SGD、USD、HKD、AUD 展示。

## 5. 房源、数据库和兼容性修改

### 5.1 Property / UnitType / Institute 三层兼容

- 搜索主数据优先使用 `UnitType + Institute + available Property/Room`。
- 只有三层模型完全没有候选时才回退旧版扁平 Property 数据。
- 推荐交互使用真实可租 `property_id`；审计同时保留 `unit_type_id`。
- 搜索只保留至少一间可租库存的户型。
- 区域可匹配 district、city、country、公寓中英文名。
- 房型兼容 studio、ensuite、1-bed、2-bed、3-bed+、shared 及中文别名。
- 房源写入兼容 `amenities → institute_amenities`、`special_offer → special_discount`。
- 创建房源的 POI 异步任务统一在 `PropertyService.create()` 中派发，删除路由层重复派发。

### 5.2 国家、币种和公开详情

- 房源列表和搜索接口增加 `country` 参数。
- 支持国家别名 SG/Singapore/新加坡、GB/UK/英国等。
- 修复新加坡房源误显示人民币符号。
- 公开房源详情从当前 `properties` 表读取，移除对已废弃 `rooms` 表的原始 SQL 依赖。
- 增加 `/room/:id` 到房源详情页的兼容别名。

### 5.3 ORM 与测试数据库兼容

以下 PostgreSQL 专用字段增加 SQLite 测试变体，生产 PostgreSQL 类型保持不变：

- JSONB → SQLite JSON。
- ARRAY → SQLite JSON。

涉及 Booking、Contract、Institute、Notification、Payment、Property、RoomType、UnitType、University 等模型。

同时完成：

- `room_commutes.room_id` 外键对齐 `properties.id`。
- 旧 `room_types.property_id` 外键对齐 `properties.id`。
- 补全 `RoomCommute`、`University` 和 Agent 新模型的 metadata 导入。
- Alembic 版本表 `version_num` 扩展到 128 字符，兼容历史超长 revision ID。

### 5.4 Agent 演示数据

新增幂等演示数据脚本 `backend/scripts/seed_agent_demo.py`，用于隔离开发环境快速建立 Agent 联调数据：

- 覆盖 SG、GB、US、HK 四个市场及 NUS、UCL、UCLA、HKU 四所大学。
- 创建公寓、房型和真实可租房间，覆盖不同币种、设施与租期。
- 可重复运行，已存在的数据会更新而不是无限重复插入。
- 脚本内包含固定演示账号和密码，只能用于隔离开发环境，不能在生产环境执行或公开部署。

## 6. 缓存与记忆的准确边界

| 能力 | 当前实现 | 生命周期 | 是否按账号隔离 |
|---|---|---|---|
| 旧版非向量房源筛选结果 | Redis | 5 分钟 | 否 |
| 文本 → Embedding | Redis | 1 小时 | 否 |
| 当前 Agent 的房源结果 | 不做结果缓存，每轮查询数据库 | 本轮请求 | 不适用 |
| Agent 会话状态 | PostgreSQL `agent_session_states` | 无 TTL | 是 |
| Agent 长期偏好 | PostgreSQL `agent_user_memories` | 无 TTL，直到删除 | 是 |
| 搜索轨迹和候选评分 | PostgreSQL search run/candidates | 无 TTL | 是 |

仓库中旧的 Redis `SearchStateManager` 定义了 2 小时 TTL，但当前 Agent 主链没有实例化或调用它，不能视为当前有效实现。

## 7. 其他同时出现在工作区的修改

以下内容不属于 Agent 搜索主链，但当前也存在于同一工作区，提交前应单独确认范围：

- 旧分步预订路由重定向到统一 `/booking/flow`。
- 新增预订授权、跨境数据、隐私、取消与退款政策页。
- 新增个人中心统计摘要服务。
- 新增订单剩余支付时间工具。
- 新增支付结果状态和重试判断工具。
- 新增个人中心失效选择清理工具。
- 新增预约与订单摘要筛选工具。
- 首页补充 API 服务导入。

对应文件：

- `frontend/src/router/index.ts`
- `frontend/src/views/policies/PolicyDocument.vue`
- `frontend/src/services/profile.ts`
- `frontend/src/utils/orderPresentation.ts`
- `frontend/src/utils/paymentResult.ts`
- `frontend/src/utils/profileSelection.ts`
- `frontend/src/utils/profileSummary.ts`
- `frontend/src/views/Home.vue`

这些文件建议不要与 Agent Memory/RAG 一次性混成同一个提交。

## 8. 验证情况

### 8.1 本次汇总时重新执行

| 检查 | 结果 |
|---|---|
| Agent、FAQ、记忆、搜索、房型、公开详情、缓存、对比评分定向回归 | `51 passed` |
| Vite 生产构建 `npm exec vite -- build` | 通过 |
| `git diff --check` | 通过 |

Vite 构建有大 chunk 警告，但没有构建失败。

### 8.2 已有真实交互验收记录

隔离 PostgreSQL 验证库和真实浏览器已经覆盖：

- NUS Studio 搜索不混入其他国家。
- “这个有健身房吗”继续指向上一轮具体房源。
- 楼内自习室与楼外附近 POI 区分。
- 长期偏好跨新会话恢复。
- 历史会话切换与刷新后恢复完整房源卡。
- FAQ chips 和站内入口。
- 国家筛选真实影响后端结果。
- 当前 6 套房源全部参与比较。
- 4,860 字浏览器输入成功；20,000 字接受，20,001 字返回 422。
- 未登录访问 `/ai-search` 跳转登录。

完整记录见 `docs/agent-search-memory-interaction-validation-report.md`。

### 8.3 尚未完全通过的检查

完整 `npm run build` 会先执行 `vue-tsc`，目前仍被项目内预订模块缺失文件、缺失测试依赖和旧 TypeScript 错误阻塞。因此当前可以确认 Vite 打包通过，但不能宣称整个前端类型检查已经全绿。

本轮没有新增前端 Vitest 自动化测试，前端交互主要依靠 Vite 构建和真实浏览器验收覆盖。

## 9. 数据库迁移状态

代码迁移 head 为 `20260802_0101`，但本机原开发库登记的 `alembic_version` 仍为 `20260722_0019`。

原开发库真实结构包含部分后续字段，存在“迁移记录与真实表结构漂移”。直接执行 `alembic upgrade head` 可能在重复字段或历史数据处理处失败，因此不能盲目升级。

上线或处理原开发库前应：

1. 先备份数据库。
2. 对照 `20260722_0019` 到 `20260725_0100` 的迁移逐项检查真实表结构。
3. 根据检查结果编写补偿迁移，或在人工确认后安全 `stamp` 对齐版本。
4. 再应用 `20260802_0101`。
5. 检查 `chat_sessions.session_kind` 的旧会话回填结果。

在迁移执行前，新代码依赖的 `session_kind` 和 4 张 Agent 表可能不存在，相关功能不能视为已在原开发库落地。

还需要注意：旧 Agent 会话目前只按标题恰好等于“租房推荐 Agent”回填，改过标题的历史会话不会自动识别；`downgrade` 会删除 4 张表中的全部记忆和审计数据；RoomType、RoomCommute 的 ORM 外键目标虽已改为 `properties.id`，本次新迁移并未同步调整真实数据库中的旧约束。

## 10. 已知限制与待处理事项

### 10.1 记忆和隐私

- 长期记忆默认启用，并会从明确搜索条件中自动学习稳定偏好。
- “清空长期记忆”只删除 `agent_user_memories`，不会删除聊天历史、会话状态或搜索审计。
- 搜索审计会保存 `original_query`，目前没有保留期、脱敏和容量清理任务。
- 单次搜索最多可写入约 120 条候选审计记录，长期运行时需要监控表增长。
- 关闭会话只清理旧的 `chat_sessions.accumulated_filters`，不会自动删除新增的 `agent_session_states`。
- `AGENT_MEMORY_ENABLED=false` 不会禁用记忆 API，只是不在对话主链中应用或自动更新长期偏好。

上线前需要明确：自动学习是否需要用户同意、保留多久、如何彻底删除以及如何监控表增长。

### 10.2 旧房源结果缓存

- 缓存 key 尚未包含 `near_lat`、`near_lng`、`near_distance_km` 和 `female_only`。
- 软删除、恢复、批量状态更新和批量软删除没有立即 bump 缓存版本。
- 受影响的是旧版非向量筛选接口；最多可能出现约 5 分钟旧结果。
- 当前 Agent 的 `search_unit_types()` 不使用这套结果缓存。

### 10.3 数据和回答边界

- 没有 POI 数据时只能确认楼内/公寓设施，不能确认楼外附近一定存在对应场所。
- 合同、押金、退款等 FAQ 目前仍属于占位政策，正式上线前需要业务确认。
- 修复前已经保存、只包含 ID/分数的旧历史消息，无法补回当时完整卡片字段。
- 20,000 字是接收上限；Embedding 和上下文打包仍会按各自预算截断。
- 确定性学校词典目前只覆盖高频学校，其他学校依赖数据库或模型识别。
- 搜索页学校与国家的前端联动目前只硬编码了 UCLA、NUS、NTU，扩展更多学校时应改为读取统一配置或后端数据。
- SSE 客户端已经支持 `AbortSignal`，但 AI 找房、搜索页 Agent 和 SmartRent 页面离开或关闭时还没有主动取消正在进行的请求。

### 10.4 已确认的代码级缺口

- 聊天内对比结果使用字段 `score`，但 Agent 推荐响应读取 `final_score`，因此对比卡综合分目前可能显示为 0；分项得分仍可返回。
- 会话列表查询会预载每个会话的全部消息，账号历史很长时可能变慢。
- AUD 已加入汇率和展示工具，但 Query Understanding 的币种白名单与澳大利亚国家推断尚未完全接通。
- 三层房源池只要存在任意候选就不会回退旧扁平房源，可能遮住仍保留在旧结构中的更匹配数据。
- 户型重排和展示主要使用 `UnitType.base_rent`；当它与真实可租房间最低价不一致时，预算贴合和展示可能产生偏差。
- 语义、POI、通勤数据缺失时目前使用中性分，不等同于该项表现差，阅读综合分时需要结合来源和缺失标记。

### 10.5 Git 与交付状态

- 当前分支与远端同名分支同步，远端最新提交仍为 `3f0bee1`。
- 8 月 2—4 日的 Memory、RAG、页面联动和验收修复尚未提交。
- 未提交工作区混有 Agent、模型兼容、预订、政策、个人中心和支付工具等多类修改。
- 在拆分、迁移验证和完整 CI 通过前，不应直接描述为“已上线”。

## 11. 建议的提交拆分

为便于 Review、回滚和生成 Issue，建议至少拆成以下提交：

1. `feat(agent): 新增会话状态与账号长期记忆`
2. `feat(search): 新增查询改写、混合召回与确定性重排`
3. `feat(agent): 增加指代解析、来源约束与事实追问`
4. `feat(frontend): 完善 Agent 历史、记忆、FAQ 与横向推荐交互`
5. `feat(search): 搜索页增加国家筛选与右侧 Agent 联动`
6. `fix(compare): 修复多币种与三层设施对比`
7. `fix(property): 对齐三层房源 ID、字段与公开详情`
8. `test(agent): 补充记忆、搜索、FAQ 与用户场景回归`
9. 将预订、政策、个人中心和支付工具另起独立提交。

按项目 Vibe Coding 规范，正式发 PR 前还需要根据最终拆分后的 diff 创建对应 Issue，并在 PR 中写入 `Closes #X`。

## 12. 关联文档

- `docs/agent-interaction-rag-upgrade-report.md`：Memory、Query Rewrite、Reranking、Grounding 等设计说明。
- `docs/agent-search-memory-interaction-validation-report.md`：最终真实浏览器与隔离数据库验收记录。
- `docs/agent-search-memory-fix-verification.md`：阶段性修复记录，后续结论以最终验收报告为准。
- `docs/search-agent-three-panel-merge-guide.md`：早期合并指导，部分内容已过时，合并时应以当前代码和最终验收报告为准。

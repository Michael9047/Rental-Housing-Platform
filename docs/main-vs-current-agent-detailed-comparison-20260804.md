# Rental Housing Platform：最新主仓库与当前工作区 Agent 全量差异审计

**审计日期：** 2026-08-04（Asia/Shanghai）
**主仓库来源：** `git@github.com:Michael9047/Rental-Housing-Platform.git`
**结论级别：** 代码、配置、数据库迁移、前端可达性与测试证据联合审计
**文档用途：** 解释两个代码快照中所有重要 Agent 差异，并给出可执行的迁移方案

---

## 1. 先看结论

本次比较必须把“Agent”拆成两类，否则会得到互相矛盾的答案。

1. **AI 编码助手与团队协作配置：两边完全相同。** 309 个相关 Git 条目逐项核对后，没有发现仅主仓库存在、仅当前工作区存在或同路径内容不同的文件。`AGENTS.md`、`CLAUDE.md`、`.claude/**`、`.qoder/**`、`.mcp/**`、`uhomes-design/**`、`.github/**` 均一致。
2. **产品里的租房 Agent：两边已经明显分叉。** 当前工作区拥有更完整的会话、长期记忆、查询理解、混合检索、确定性重排、约束放宽、来源追踪、真正的 token 流式输出和搜索页三栏联动；最新主仓库拥有更新的 `Institute → UnitType` 房源模型、Institute 级 POI/通勤、大学近距搜索、Google Maps 和建筑详情体系。
3. **当前 Agent 代码不能整分支合入最新 `main`，也不能按大文件覆盖。** 两边对“推荐结果 ID 到底代表 Room、Property、UnitType 还是 Institute”的理解不同，购物车、POI、通勤、详情路由和迁移图都存在硬冲突。
4. **最新主仓库自身也有阻断性 Agent 缺陷。** `AgentCartItem` 已迁移到 `unit_type_id`，但 `CartService` 和 API 仍访问 `property_id/property`；测试元数据仍保留 `embedding_jobs.property_id → properties.id`，而最新模型已经没有 `properties` 表，导致 Agent 测试在建表阶段全部报错。
5. **正确方向是以最新 `main` 为底座，按能力移植当前 Agent。** 先统一 ID 语义并修复主仓库基线，再重建迁移，随后适配记忆、检索、API、前端和测试；不要直接 merge 当前工作树，也不要把当前 `Search.vue` 覆盖到主仓库。

### 1.1 一页式判断矩阵

| 维度 | 最新主仓库 | 当前工作区 | 本次判断 |
|---|---|---|---|
| 编码助手规则 | 与当前一致 | 与主仓库一致 | 无跨仓库差异，但有共同缺陷 |
| Agent 会话体验 | 单次、轻量 | 多会话、历史回放 | 当前明显更强 |
| 长期记忆 | 无 | 有，支持读/写/清空 | 当前独有 |
| 查询理解 | 基础意图和筛选 | Rewrite、指代解析、状态合并 | 当前更强 |
| 检索与排序 | 新模型数据更丰富，但链路较基础 | 混合召回、消融、七信号重排 | 当前逻辑更强，主仓库数据底座更新 |
| 来源与可观测性 | 很有限 | 搜索运行、候选分数、来源记录 | 当前更强，但前端展示未完全接通 |
| 流式响应 | 搜索正文主要是模拟分块 | LLM token 真实流式 | 当前更强 |
| 房源数据模型 | `Institute → UnitType`，Room 已删除 | 仍保留 `properties/Room` 兼容层 | 主仓库是目标模型 |
| POI / 通勤 | Institute 级 | Room/Property 级 | 不能直接兼容 |
| 搜索地图 | Google Maps、大学半径搜索 | 三栏 Agent，但地图实现有风险 | 两边各有必须保留的能力 |
| Agent 自动测试 | 基线建表失败 | 31 项通过 | 当前测试更完整，但基于旧模型 |
| 合并策略 | 作为底座 | 作为能力来源 | 重新适配，不整包合并 |

---

## 2. 比较基线与文件位置

为了让报告可复核，以下用两个缩写表示仓库根目录：

- **`[MAIN]`**：`/Users/shenjack/Documents/Rental-Housing-Platform-main-20260804`
- **`[WORK]`**：`/Users/shenjack/Documents/rental house`

### 2.1 主仓库快照

| 项目 | 值 |
|---|---|
| 本地位置 | `/Users/shenjack/Documents/Rental-Housing-Platform-main-20260804` |
| 远程仓库 | `Michael9047/Rental-Housing-Platform` |
| 分支 | `main` |
| HEAD | `78de6ec93ff9120574a36c50488b3be74ef300f1` |
| 提交时间 | 2026-08-04 16:42:02 +08:00 |
| 提交标题 | `fix: Vite 代理端口 8001→8000` |
| 工作区状态 | 干净 |
| 大小 | 约 32 MB |

原 SSH 地址在当前执行环境中无法完成克隆，因此改用同一 GitHub 仓库的 HTTPS 只读地址完成下载。仓库内容和提交身份不因传输协议变化而变化。

### 2.2 当前工作区快照

| 项目 | 值 |
|---|---|
| 本地位置 | `/Users/shenjack/Documents/rental house` |
| 分支 | `feat/agent-search-compare-update` |
| HEAD | `3f0bee15dec28681fcb1f873585090fd587137ea` |
| 提交时间 | 2026-07-29 20:52:49 +08:00 |
| 提交标题 | `revert(agent): 推荐提示词恢复 3b426e0 口语化长文版` |
| 未提交状态 | 38 个已跟踪路径有修改，26 个未跟踪条目 |

当前工作区的 Agent 核心增强大多仍处于**未提交状态**。因此，本报告比较的是“当前磁盘上的完整工作树”，不只是 `3f0bee1` 提交。若只检出该分支 HEAD，将无法重现本文所述的记忆、检索和三栏联动能力。

### 2.3 两条历史已经大幅分叉

两个快照都包含共同提交 `2e48d05a743030c0ac67ccdab7e7faf5d29182e8`（2026-07-24）。从该点向后：

- 当前功能分支有 5 个已提交提交，外加大量未提交修改。
- 最新 `main` 有 97 个提交。

这意味着差异不是简单的“当前分支比主仓库多一项功能”。两边在同一基线后分别继续演进：当前分支重点建设 Agent 智能链路，`main` 重点推进房源模型、地图、建筑详情和业务模块。

---

## 3. 审计范围、方法与限制

### 3.1 审计范围

本次覆盖：

- 根级协作规则：`AGENTS.md`、`CLAUDE.md`、README、`.gitignore`。
- Claude 配置与 Skills：`.claude/**`。
- Qoder 知识库：`.qoder/**`。
- MCP 命名目录：`.mcp/**`。
- uhomes 设计 Skill：`uhomes-design/**`。
- GitHub 协作自动化：`.github/**`。
- 产品 Agent 后端：路由、Schema、模型、服务、编排、检索、记忆、对比、购物车。
- 数据层：SQLAlchemy 元数据与 Alembic 迁移图。
- 产品 Agent 前端：路由、页面、组件、Service、Pinia Store、TypeScript 类型。
- Agent 文档、HTML 联调页和自动测试。
- 与 Agent 合并直接相关的新房源模型、POI、通勤、搜索地图和详情路由。

### 3.2 使用的方法

1. 对配置范围内的 Git 路径、文件模式和 blob ID 做逐项核对。
2. 对实际文件系统做递归比较，以覆盖当前未提交内容。
3. 对关键文件逐行阅读，并记录精确行号。
4. 比较 Agent 服务文件数、行数、API 端点和数据 Schema。
5. 检查 SQLAlchemy 外键能否在当前 Base metadata 中解析。
6. 检查 Alembic revision 数量和 head。
7. 从路由和 import 关系确认前端代码是否真实可达，而非只看文件是否存在。
8. 执行当前工作区 Agent 测试组，并在主仓库隔离副本中执行 Agent 测试。

### 3.3 重要限制

- 未比较用户主目录中的个人级 Codex、Claude、Cursor 或 MCP 配置；结论仅针对仓库内可见配置。
- 未对生产数据库执行任何迁移，也没有修改主仓库克隆。
- 主仓库测试被 SQLAlchemy 元数据错误阻断，因此无法据此证明其 Agent 业务逻辑本身全部失败；能确定的是它当前无法进入测试正文。
- 当前工作区测试通过并不代表代码可直接运行在最新 `main` 数据库上，因为两边模型和迁移图不同。

---

## 4. 第一类 Agent：AI 编码助手与团队协作配置

### 4.1 跨仓库差异结果：零

共核验 309 个相关 Git 条目：

| 范围 | 条目数 | 比对结果 |
|---|---:|---|
| `.claude/**` | 14 | 完全相同 |
| `.qoder/**` | 266 | 完全相同 |
| `.mcp/**` | 1 | 完全相同 |
| `uhomes-design/**` | 12 | 完全相同 |
| `.github/**` | 10 | 完全相同 |
| 根规则、README、ignore、两份 Agent 后端文档 | 6 | 完全相同 |
| **合计** | **309** | **无跨仓库差异** |

因此，“主仓库的 AGENTS/Claude/Qoder 配置和我们现在不一样”这一假设不成立。两边复制的是同一套规则和素材。

### 4.2 `AGENTS.md`：相同，但后半段已经损坏

两边 `AGENTS.md` 的 Git blob 都是 `ac5c99caa2a777c591dc3ca5b81f0add2699692c`。

可读部分定义了：

- 分支命名与禁止直接在 `main` 开发：`AGENTS.md:7-21`。
- Conventional Commits 和中文说明：`:25-52`。
- 项目结构：`:56-85`。
- Python/Vue 代码风格：`:89-106`。
- 模块中文标准名：`:110-128`。
- “先开发、发 PR 时再建 Issue”的 Vibe Coding 流程：`:135-190`。
- PR、环境变量、冲突和迁移规则：`:195-226`。

共同问题在 `AGENTS.md:228-262`：文件中实际存储的是 ASCII 问号，不是终端编码显示错误。原中文已经丢失，不能靠切换 UTF-8 或 GBK 恢复。前半段保留了大部分重复规则，所以短期仍可工作；但只存在于损坏部分的细节会被 AI 忽略。

### 4.3 `CLAUDE.md`：相同，但与 `AGENTS.md` 并非真正一致

两边 blob 都是 `da280200df5ba5d3e29c6aa652ae31134820152c`。

Claude 版本额外写了：

- `gh issue create` 示例：`CLAUDE.md:101-124`。
- PR 模板和 `Closes #X`：`:126-140`。
- 前端截图门禁：`:145-149`。
- 依赖管理：`:169-173`。
- 不自动推送、不删除测试、不擅自升级依赖：`:177-183`。

但该文件也在 `:185-190` 出现实际问号乱码，并把“自行决定”一句从中间截断。更重要的是，仓库没有声明 `AGENTS.md` 与 `CLAUDE.md` 冲突时以哪个为准。结果是不同助手可能执行不同的截图、Review 或推送边界。

### 4.4 `.claude/settings.json`：相同，但权限明显过宽

两边 blob 都是 `8f23316c2de932e4049258b7e48f396e13dceb88`。

该文件允许 Claude 自动使用 `git`、`curl`、`python`、`gh`、`docker`、包管理器、测试、Alembic、WebFetch、WebSearch、Agent 以及 PowerShell 的 `Remove-Item`、`Stop-Process` 等，还允许读写 `.env`，且没有显式 deny。

影响不是“主仓库和当前谁更强”，而是**两边共同拥有同样的安全面**：

- `git:*` 可能覆盖破坏性 Git 操作。
- `python:*` 等价于允许执行任意脚本逻辑。
- `.env` 读取、网络请求和通用命令同时开放，会扩大秘密误用风险。
- `Remove-Item` 与 `Stop-Process` 不适合作为仓库默认无确认权限。

`.claude/settings.local.json` 被 `.gitignore:28-29` 忽略，两边本机当前均没有该覆盖文件。

### 4.5 Claude Skills：内容相同，共同存在三个结构问题

两边都有 10 个基础 UI Skill 和一个 `meta-refactor-ui` 编排 Skill，内容一致。

**问题一：失效 Gitlink。** `.claude/skills/refactoring-ui-plugin` 是 mode `160000` 的 Gitlink，指向 `00781eab...`，但仓库没有 `.gitmodules`。Fresh clone 无法知道其上游 URL，也无法初始化。

**问题二：不存在的注册表。** `meta-refactor-ui/SKILL.md:37-41` 要求读取 `skills.json` 并验证 10 个 Skill，但两边都没有该文件。

**问题三：间距规则冲突。** 通用 spacing Skill 规定 16px 基准和 `4/8/12/16/...` 序列，而 `uhomes-design/SKILL.md:191-200` 规定 5px 基准和所有尺寸为 5 的倍数。仓库没有写优先级，同一次 UI 任务可能获得互相冲突的建议。

### 4.6 `uhomes-design`：相同，但难以自动触发且内部自相矛盾

两边 `uhomes-design/SKILL.md` blob 都是 `75e72211...`，目录中 12 个跟踪文件一致。

共同问题：

1. `uhomes-design/CLAUDE.md` 位于 `frontend` 的兄弟目录，根 `CLAUDE.md` 又没有强制引用；编辑前端时不能保证自动加载。
2. 该 Skill 不在标准 `.claude/skills/uhomes-design/` 位置，更像人工参考包。
3. `screens/`、`screenshots/`、`fonts/` 被 `.gitignore:33-37` 整体忽略，Fresh clone 缺少 Skill 要求研究的截图和字体。
4. `SKILL.md:135-181` 说标题用 `cfont`、正文用 `Poppins`，`:185` 又完全反转。
5. `SKILL.md:524` 声明 accent 未提取，却在 `:314`、`:887-892`、`:918` 使用未定义的 `var(--accent)`。
6. 约 72 KB 的单一 Skill 又嵌入大量 reference 内容，重复信息和失效路径会浪费上下文并加剧冲突。

### 4.7 `.qoder`：相同，但知识快照陈旧

两边都有 266 个相同的 RepoWiki 文件，约 4.7 MB。索引 `.qoder/repowiki/knowledge/en/_index.yaml` 标记导出时间为 2026-07-05、分支为 `main`，对应最后代码提交 `75ff1a37...`。

该快照比当前功能分支 HEAD 落后约 181 个提交，比最新主仓库落后约 273 个提交。它不是运行权限配置，而是旧版项目知识；继续把它当最新架构，会让 Qoder理解过时的 API、模型和目录。

### 4.8 `.mcp`：相同，而且并没有 MCP 配置

两边 `.mcp` 只有同一张 `uhomes_screenshot.png`，没有 `mcp.json`、`.mcp.json`、server、transport、command 或环境配置。因此这个目录名不能证明项目接入了 MCP。

### 4.9 两边都没有的专用配置

仓库内都没有 `.codex/`、`.agents/`、`.cursor/`、`.cursorrules`、Copilot instructions、Windsurf、Aider、Gemini、Roo 或正式 MCP JSON 配置。Codex 主要依赖根 `AGENTS.md`；Claude 是唯一拥有专属仓库权限和 Skill 目录的编码助手。

### 4.10 GitHub 配套：相同，只有部分规则被自动强制

- `.github/PULL_REQUEST_TEMPLATE.md:12-53` 包含 AI 声明、Issue、测试、迁移、依赖、截图和规范检查。
- `.github/CODEOWNERS:134` 只明确覆盖 `/AGENTS.md`，没有同等覆盖 `CLAUDE.md`、`.claude/**` 和设计 Skill。
- `branch-name-check.yml:16-49` 真正执行分支命名规则。
- `project-automation.yml:47-65` 识别 `Closes #X` 并在 PR 合并后尝试移动 Issue。
- 目前没有 workflow 强制每个 PR 必须写 `Closes #X`、必须完成 AI 声明或必须附前端截图。

---

## 5. 第二类 Agent：产品内租房 Agent 总体架构

### 5.1 两条实际链路

最新主仓库的主链较短：

```text
用户消息 → Router/Dispatcher → Search/Compare/FAQ/Cart → 数据库与 LLM → 回复/推荐卡
```

当前工作区把搜索主链扩展为：

```text
用户消息
  → 会话历史与长期记忆装载
  → Query Understanding / Rewrite
  → 指代解析与对话状态合并
  → 结构化候选池 + 向量/词法召回
  → 硬约束筛选与最小约束消融
  → 七信号确定性重排
  → Context Packing
  → Grounded Answer + 来源清单
  → 真正 SSE token 流
  → 搜索审计、候选分数、历史元数据持久化
```

但是当前链路仍依赖旧的 Room/Property 模型，而最新 `main` 已转向 `Institute → UnitType`。所以“算法链路更完整”和“数据模型更新”分别发生在两条分支上。

### 5.2 后端规模变化

| 指标 | 最新主仓库 | 当前工作区 |
|---|---:|---:|
| `backend/app/services/agentic` Python 文件 | 22 | 27 |
| 代码行数 | 6,403 | 9,332 |
| Agent API 路由文件 | 285 行 | 618 行 |
| Agent Pydantic Schema | 163 行 | 270 行 |
| Agent 前端主页面 `AiSearch.vue` | 224 行 | 727 行 |
| Agent Pinia Store | 64 行 | 202 行 |
| Agent TypeScript 类型 | 136 行 | 273 行 |

当前工作区新增的五个核心服务文件是：

- `agentic/context.py`：历史压缩、候选上下文和用户可见来源。
- `agentic/guided_search.py`：POI 软排序和渐进筛选选项。
- `agentic/memory.py`：会话状态、长期记忆、指代解析、搜索审计。
- `agentic/query_understanding.py`：查询改写、字段增删和 LLM/规则降级。
- `agentic/retrieval.py`：过滤、约束消融、词法相关度、七信号重排和来源 manifest。

---

## 6. 后端逐能力差异

### 6.1 会话列表与历史回放

最新主仓库只提供创建会话和发送消息。当前在 `[WORK]/backend/app/api/v1/routes/agent.py:197-292` 增加：

- `GET /sessions`：按更新时间列出当前用户 Agent 会话。
- `GET /sessions/{session_id}/messages`：按时间正序回放历史，支持 `before_id`。

对应 Schema 位于 `[WORK]/backend/app/schemas/agent.py:18-50`。

影响：当前可以刷新后继续、切换旧会话并恢复推荐卡元数据；主仓库每次进入更接近新建一次性对话。当前实现仍有分页缺口：前端固定最多拉 50 个会话和 100 条消息，没有消费 `total/has_more`。

### 6.2 短期对话状态

当前新增 `AgentSessionState`，见 `[WORK]/backend/app/models/agent_intelligence.py:25-46`，记录：

- 阶段 `stage`。
- 累积筛选 `filters_json`。
- 指代映射 `reference_map_json`。
- 最近搜索 `last_search_json`。
- 滚动摘要 `rolling_summary`。
- 上下文版本 `context_version`。

最新主仓库没有对应表。其 Dispatcher 主要加载最近 10 条消息，见 `[MAIN]/backend/app/services/agentic/dispatcher.py:231-241`，缺少结构化状态和稳定指代映射。

### 6.3 跨会话长期记忆

当前新增 `AgentUserMemory`，见 `[WORK]/backend/app/models/agent_intelligence.py:49-62`，每个用户一行，保存带置信度和证据次数的偏好。

`[WORK]/backend/app/services/agentic/memory.py:167-243` 实现：

- 只应用置信度至少 0.75 的记忆。
- 用户显式保存时置信度设为 1。
- 可以覆盖、合并或清空长期偏好。

API 位于 `[WORK]/backend/app/api/v1/routes/agent.py:293-339`：

- `GET /memory`
- `PUT /memory`
- `DELETE /memory`

最新主仓库完全没有这套能力。影响是主仓库无法在新会话自动记得国家、学校、房型等稳定偏好。

### 6.4 对话筛选合并和清除语义

当前 `[WORK]/backend/app/services/agentic/memory.py:90-164` 支持：

- “不限区域”“取消预算”“不要之前的条件”等字段删除。
- “重新开始/清空条件”整体重置。
- 长期记忆 < 会话状态 < 本轮理解 < 前端显式值的优先级。
- 列表字段默认增量合并，只有明确取消才移除。

这解决了多轮对话中后一条短句静默覆盖前面条件的问题。最新主仓库没有等价的结构化合并层。

### 6.5 查询理解与 Query Rewrite

当前 `[WORK]/backend/app/services/agentic/query_understanding.py:12-376` 增加独立查询理解模块：

- 输出 `exact / relative / reference / exploratory` 查询类型。
- 提取新增条件、删除字段和删除值。
- 将上一轮有效状态写入重写后的检索表达。
- LLM 不可用或 JSON 不合法时走确定性规则降级。

Dispatcher 在 `[WORK]/backend/app/services/agentic/dispatcher.py:262-283` 先完成 rewrite，再进入搜索。API 对外返回 `query_rewrite`，Schema 位于 `[WORK]/backend/app/schemas/agent.py:166-172`。

最新主仓库的 SearchAgent 虽然把 `query_rewrite` 列为工具名，但没有这套独立、可回退、可对外说明的执行链。

### 6.6 指代解析

当前 `[WORK]/backend/app/services/agentic/memory.py:246-300` 解析：

- “第二套 / 第 2 个”。
- “最便宜的 / 最近的 / 最大的 / 综合最好的”。
- “刚才那套 / 这个 / 它”。

解析结果通过 `ReferenceResolutionInfo` 返回，见 `[WORK]/backend/app/schemas/agent.py:174-179`。最新主仓库只做较简单的显式 ID 提取，没有结构化的序号和语义引用表。

### 6.7 候选召回

当前 SearchAgent 同时保留结构化查询、向量/词法相关度和旧 Property 兼容池，并在 `[WORK]/backend/app/services/agentic/retrieval.py` 统一过滤和重排。

优势：

- 可以先扩大候选池，再统一施加硬约束和软偏好。
- LLM/embedding 不可用时仍可用词法和结构化检索。
- 检索池大小由 `AGENT_RETRIEVAL_POOL_SIZE` 控制。

风险：当前仍保留三层候选来源和 legacy Property fallback；在最新主仓库中 `Property` 已只是 `UnitType` 别名，这个 fallback 可能重复、遮蔽或错误解释候选。

### 6.8 约束消融与最小放宽

当前 `[WORK]/backend/app/services/agentic/retrieval.py:182-260` 对零结果或结果过少执行 constraint ablation：

- 逐个试验可以放宽的字段。
- 记录每次试验前后数量和解释。
- 只应用能以最小代价恢复结果的放宽。
- 将 `relaxation_trace` 和可点击选项返回前端。

最新主仓库基本直接返回结果或“尝试放宽”，没有同等级别的可审计放宽轨迹。

### 6.9 七信号确定性重排

当前 `[WORK]/backend/app/services/agentic/retrieval.py:301-414` 计算并记录多个确定性信号：

- 预算/价格。
- 通勤。
- 设施匹配。
- POI 偏好。
- 词法相关度。
- 数据质量/完整度。
- 向量或基础召回分。

最终分数、分项和名次写入推荐结果：`AgentRecommendation.rank/final_score/score_breakdown`，见 `[WORK]/backend/app/schemas/agent.py:123-133`。

最新主仓库已有基础评分与更丰富的 embedding 文本，但没有当前这套统一、可追踪的最终 reranker。

### 6.10 Context Packing

当前 `[WORK]/backend/app/services/agentic/context.py:16-54` 按字符预算装载历史；`:56-122` 将候选、条件、放宽轨迹和 grounding policy 打包给 LLM。预算由：

- `AGENT_HISTORY_CHAR_BUDGET=8000`
- `AGENT_CONTEXT_CHAR_BUDGET=12000`

控制。主仓库主要按固定消息条数加载历史，不具有同等可控的上下文压缩。

### 6.11 Grounded Answer 与来源

当前要求回答只能使用候选包里的已标注事实，缺失字段必须说“数据暂缺”，不能从价格或房型猜设施。关键位置：

- `[WORK]/backend/app/services/agentic/agents/search_agent.py:347-354`：Grounding 规则。
- `:838-930`：放宽、重排、来源 manifest 和候选快照。
- `[WORK]/backend/app/services/agentic/context.py:124-147`：用户可见来源。
- `[WORK]/backend/app/services/agentic/dispatcher.py:496-569`：搜索执行与 grounded 结果。

最新主仓库会附加简短检索说明，但缺少逐候选的 `source_metadata` 和统一来源清单。

需要区分“后端已返回”和“前端已展示”：当前可达的 `/ai-search` 与 Search 右侧面板会保存 `sources`，却没有真正渲染全部来源；只有未路由的 `SmartRentView.vue` 展示来源 chips。

### 6.12 真正的 SSE token 流

最新主仓库 `[MAIN]/backend/app/services/agentic/dispatcher.py:154-188` 对搜索回复采用“先生成完整回复，再每 3 个字 yield”的模拟流式。

当前 `[WORK]/backend/app/services/agentic/agents/search_agent.py:1039-1087` 直接消费 LLM 流并逐 token yield；`[WORK]/backend/app/services/agentic/dispatcher.py:905-1029` 先发执行状态、再发 token、最后发结构化 meta。

用户影响：当前首字等待更短，取消和中断更自然，也能在文本未结束前持续看到真实生成进度。

### 6.13 搜索审计与可观测性

当前新增：

- `AgentSearchRun`：原始/改写查询、有效条件、放宽轨迹、来源、候选数、选中数、耗时，见 `[WORK]/backend/app/models/agent_intelligence.py:65-92`。
- `AgentSearchCandidate`：候选 ID、名次、总分、分项和来源，见 `:95-124`。

最新主仓库没有这两张表。它无法稳定回答“为什么这套排第一”“哪个条件被放宽”“某次搜索用了什么数据源”。

### 6.14 渐进选房与 POI 引导

当前 `[WORK]/backend/app/services/agentic/guided_search.py:89-197` 支持：

- 按地铁、超市、医院、健身房等真实 POI 距离做软排序。
- 只提供候选池中确实有数据的引导 chip。
- 结果足够多时提供“再便宜点”“独立卫浴”等收窄选项。

但该文件的模型假设已经过时：`:9-11` 和 `:35-67` 明确通过 `Room → PropertyPOI` 汇总到 UnitType。最新主仓库已经删除 Room 表，POI 改为 `InstitutePOI`。直接复制后查询会失败或静默降级为空。

### 6.15 通勤数据

当前 SearchAgent 在 `[WORK]/backend/app/services/agentic/agents/search_agent.py:493-550` 通过 `RoomCommute` 补通勤。

最新主仓库的新模型是 `[MAIN]/backend/app/models/institute_commute.py:10-25`，主键是 `institute_id + university_id`。然而主仓库 SearchAgent 自身仍在 `[MAIN]/backend/app/services/agentic/agents/search_agent.py:762-780` 尝试 `RoomCommute.room_id` 和 `Room.unit_type_id`，异常被捕获后静默降级。

结论：两边的 Agent 通勤实现都不是最终正确版本。迁移时应直接查询 `InstituteCommute`，不要保留 Room 桥接。

### 6.16 对比 Agent

当前 `compare_agent.py` 增加真实币种、设施、POI、评分分项和更严格的可解释输出；对比 API 允许前端传选中的当前结果 ID，而不必先全部加入购物车。

但最新主仓库以 UnitType ID 为核心，当前接口字段和 Schema 仍名为 `property_id/property_ids`。如果不先统一 ID，用户勾选的 12 可能在某处被解释为 UnitType 12、另处被解释为旧 Property 12，造成对比错对象。

### 6.17 购物车是当前最明确的 P0 冲突

最新主仓库：

- `[MAIN]/backend/app/models/agent_cart.py:25-41` 的 `AgentCartItem` 只有 `unit_type_id` 和 `unit_type`。
- `[MAIN]/backend/app/services/agentic/agents/cart_agent.py:35-64` 仍查询 `AgentCartItem.property_id`，并用 `property_id=` 构造对象。
- `[MAIN]/backend/app/api/v1/routes/agent.py:193-246` 及 Schema 仍围绕 `property_id/property` 序列化。

这会在真正调用购物车时产生属性或构造错误。当前工作区的 CartService 与旧 `properties` 表是一致的，但不能直接解决最新模型问题。

正确修复应统一改为 `unit_type_id/unit_type`，并在 API 层明确是否暂时保留 `property_id` 兼容别名。

### 6.18 主仓库 CompareAgent 也没有完成 UnitType 迁移

最新主仓库中的 `Property` 实际已经是 UnitType 别名，但 CompareAgent 仍读取旧字段：

- `price_monthly`：`[MAIN]/backend/app/services/agentic/agents/compare_agent.py:186,332`。
- `title`：`:214,320,336`。
- `PropertyPOI.property_id`：`:149-151`。
- 从购物车读取 `item.property_id`：`:130`。

UnitType 的真实字段是 `base_rent/name/institute_id`。POI 错误位于 `try/except` 中时可能静默退化为“无 POI”，但 `price_monthly/title` 没有等价保护，显式对比两个 UnitType 仍可能直接失败。

此外，主仓库 `tool_registry.py:430-431,689,738-739` 和 `supervisor.py:731,737` 仍存在 `property_id/prop.title/prop.price_monthly/item.property` 等旧合同。修复范围不能只限于 CartService 和 API。

### 6.19 两边的 embedding 路线也不同

最新主仓库：

- `UnitType.embedding` 是 Text，通常存 JSON 字符串。
- `build_unit_type_search_text()` 位于 `[MAIN]/backend/app/services/agentic/agents/search_agent.py:111-245`，包含 Institute、UnitType、设施、POI、通勤和 safety，语义文本更丰富。
- `scripts/build_rag_embeddings.py:56-127` 加载 POI、安全和通勤后生成 embedding。
- 搜索先取最多 500 行，见 SearchAgent `:685-696`，再在应用层动态导入 numpy 逐条算余弦，见 `:698-721`。

当前工作区：

- Room 和 UnitType embedding 使用 `Vector(1536)`。
- `property_service.py:405-409,487-492` 把 cosine distance 下推数据库。
- `20260725_0100_embedding_vector_hnsw.py:69-85` 创建 HNSW cosine 索引。

主仓库方案的富文本更好，但应用层全量排序随数据线性增长，而且 `requirements.txt` 没有声明 numpy；当前方案的 pgvector/HNSW 更适合规模化。最佳整合是：采用主仓库有事实来源的富文本，采用当前的 Vector + HNSW + hybrid retrieval。

### 6.20 主仓库富文本中存在无来源画像

`[MAIN]/backend/app/services/agentic/agents/search_agent.py:35-89` 会从建筑类型和设施推导“高端学生社区”“居民以中高收入人群为主”“本地家庭为主”“生活成本低”等描述。

这些并非数据库直接事实，存在偏见、Grounding 和解释风险。迁移时应保留 POI、安全、通勤、设施等可验证事实，删除居民收入、阶层或人群构成推断。

### 6.21 当前搜索仍有四个算法边界

1. **旧 Room fallback 可能漏结果。** `[WORK]/backend/app/services/agentic/agents/search_agent.py:801-816` 只有 UnitType 候选池完全为空才查旧 Room；部分迁移状态下，未迁移 Room 会被遮蔽。
2. **消融只尝试一个字段。** `[WORK]/backend/app/services/agentic/retrieval.py:196-259` 可解释性好，但无法发现“同时放宽预算和区域才有结果”。
3. **设施同义词不足。** `retrieval.py:61-65,140-143` 主要依赖规范化后精确相等，`WiFi/无线网络`、`ensuite/独卫`、`furnished/家具齐全` 可能互不匹配。
4. **附近设施可能误报 missing。** `[WORK]/backend/app/services/agentic/dispatcher.py:462-474,1018-1028` 可能在候选已有 `_poi_distances` 时仍追加“楼外周边 POI missing”。

这些不是否定当前方案，而是迁移到新模型时应顺便收紧的边界。

### 6.22 长期记忆需要隐私、容量和并发治理

当前默认 `AGENT_MEMORY_ENABLED=true`，见 `[WORK]/backend/.env.example:35`。稳定字段包括国家、学校、房型、通勤方式和 `female_only`，见 `memory.py:30-35`。第一次明确表达的稳定字段可获得 0.78 置信度，见 `memory.py:511-518`，高于 0.75 的自动应用阈值。

这意味着用户只搜索一次“NUS 附近的 studio”，某些偏好就可能跨会话自动生效，而不是只有显式 `PUT /memory` 才保存。当前还没有：

- 清晰的首次告知和单独的“自动学习”开关。
- TTL 或定期清理。
- 原始查询裁剪/脱敏；最长 20,000 字可写入搜索审计。
- 搜索 run/candidate 容量保留策略。
- 记忆导出机制。

并发方面，`memory.py:396-428` 采用“先 SELECT，不存在则 INSERT + flush”，同时数据库对 session/user 有唯一约束，但没有 upsert、`FOR UPDATE` 或 IntegrityError 重试。同一用户首次并发请求可能竞争唯一约束或互相覆盖状态。

### 6.23 历史和元数据持久化有性能与一致性风险

`GET /sessions` 在 `[WORK]/backend/app/api/v1/routes/agent.py:209-242` 使用 `selectinload(ChatSession.messages)`，然后在 Python 中加载并排序每个会话的全部消息，只为计算条数和最后一条。历史 metadata 还可能携带完整推荐卡，数据增长后会明显变重。

同步接口的 `_update_latest_history_metadata()` 位于 `:170-192`，按 `session_id + assistant role + id DESC` 找最新回复。同一会话并发发送两条消息时，请求 A 可能把 metadata 写到请求 B 的回复。更稳妥的设计是 Dispatcher 返回本次 assistant message ID，并按精确 ID 更新。

### 6.24 当前核心模块仍未纳入 Git

截至审计时，`context.py`、`memory.py`、`query_understanding.py`、`retrieval.py` 等是未跟踪文件，但已跟踪的 `dispatcher.py:18-25`、`search_agent.py:609-624` 和 `supervisor.py:804,928` 已导入它们。

如果只提交 `git diff` 中的已跟踪修改而漏掉 `??` 文件，部署会在 import 阶段直接失败。这是交付流程层面的 P0，必须在拆分提交时核对新增文件。

---

## 7. API 与数据合同差异

### 7.1 端点差异

| 能力 | 最新主仓库 | 当前工作区 |
|---|---|---|
| 新建会话 | `POST /sessions` | 相同，但标记 `session_kind=agent` |
| 会话列表 | 无 | `GET /sessions` |
| 历史消息 | 无 | `GET /sessions/{id}/messages` |
| 长期记忆读取 | 无 | `GET /memory` |
| 长期记忆保存 | 无 | `PUT /memory` |
| 长期记忆清空 | 无 | `DELETE /memory` |
| 同步消息 | 有 | 扩展 `context_filters/mode` 和结果元数据 |
| 流式消息 | 有 | 真 token 流 + 状态 + 最终 meta |
| FAQ | 有 | 有 |
| 购物车 CRUD | 有但 ID 实现冲突 | 有，基于旧 Property |
| 对比 | 有 | 增强评分、POI 和显式 ID |

### 7.2 请求 Schema

最新主仓库的 AgentFilter 主要是基础价格、区域、卧室、类型和部分租房条件。当前 `[WORK]/backend/app/schemas/agent.py:54-93` 扩展到：

- 国家与币种。
- 设施、房型、卫浴、面积。
- 最短/最长租期、入住日期。
- POI 条件。
- 通勤方式和分钟数。
- 学校、女性限定。
- 硬约束/软偏好字段清单。

当前 `AgentMessageRequest` 把输入上限提高到 20,000 字，并增加 `context_filters`、`compare_property_ids` 和兼容 `mode`，见 `:95-106`。

### 7.3 响应 Schema

当前每个推荐新增：

- `rank`
- `final_score`
- `score_breakdown`
- `poi_distances`
- `source_metadata`

当前每次回复新增：

- `guided_options`
- `raw_intent`
- `stage`
- `sources`
- `relaxation_trace`
- `query_rewrite`
- `reference_resolution`
- `state_summary`
- `filter_patch`

这些字段支持可解释搜索和三栏联动，但也扩大了后端、前端和历史元数据之间的合同面积。迁移时必须用契约测试固定字段，而不能仅靠 TypeScript 编译。

### 7.4 `PropertySearchResult` 兼容层

当前 `[WORK]/backend/app/api/v1/routes/agent.py:59-167` 同时支持 UnitType 与旧 Property/Room，并将 UnitType 映射成 `PropertySearchResult`。

这在过渡期方便，但有三个问题：

1. `landlord_id=0` 是占位值，不是真实业务数据。
2. `property_id` 可能是 UnitType ID，也可能是旧 Property ID。
3. 主仓库已经把 `Property` 变成 UnitType 兼容别名，继续保留两种语义只会扩大歧义。

建议在最新 `main` 上定义一个新的、实体语义清晰的 Agent recommendation DTO，例如明确字段 `unit_type_id` 和 `institute_id`，再为旧前端提供短期兼容字段。

---

## 8. 数据模型与数据库迁移冲突

### 8.1 房源主实体已经改变

当前工作区：

- `[WORK]/backend/app/models/property.py` 中 `Room.__tablename__ = "properties"`。
- 每个可租房间可以独立有价格、地址、房东、图片、embedding。
- `Property = Room` 作为旧名兼容。

最新主仓库：

- `[MAIN]/backend/app/models/property.py` 只是兼容桥，`Property` 和 `Room` 都别名到 `UnitType`。
- `[MAIN]/backend/app/models/unit_type.py` 才是租赁核心实体。
- `UnitType` 归属于 `Institute`，Room 表已经删除。

这不是字段小改，而是实体边界重构。所有 ID、外键、URL 和候选清单都必须随之重新定义。

### 8.2 POI 归属改变

| 当前工作区 | 最新主仓库 |
|---|---|
| `PropertyPOI` | `InstitutePOI` |
| 外键 `property_id → properties.id` | 外键 `institute_id → institutes.id` |
| 每个房间/Property 一份 POI | 每栋公寓/Institute 一份 POI |

周边设施本质上通常属于建筑位置，而不是某个户型。主仓库的新设计更合理，当前 `guided_search.py` 应改为 `UnitType.institute_id → InstitutePOI`。

### 8.3 通勤归属改变

| 当前工作区 | 最新主仓库 |
|---|---|
| `RoomCommute(room_id, university_id)` | `InstituteCommute(institute_id, university_id)` |
| 通勤随房间重复 | 同一建筑共享通勤 |

迁移应删除 Room 级 join，避免重复数据和已删除字段。

### 8.4 Agent 搜索审计表需要重新设计外键

当前 `AgentSearchCandidate` 同时有：

- `unit_type_id → unit_types.id`
- `property_id → properties.id`

见 `[WORK]/backend/app/models/agent_intelligence.py:95-122`。

最新主仓库没有 `properties` 表，因此 `property_id` 外键无法存在。建议在目标模型中：

- 只保留 `unit_type_id` 作为候选主键。
- 如需要建筑聚合，再加 `institute_id`。
- 不再创建 `property_id → properties.id`。

### 8.5 Alembic 迁移图完全不同

| 指标 | 当前工作区 | 最新主仓库 |
|---|---:|---:|
| migration Python 文件 | 74 | 88 |
| Alembic head | `20260802_0101` | `8c314438f8b1` |
| 当前记忆迁移的 parent | `20260725_0100` | 最新图中不存在该 revision |

当前新增迁移 `[WORK]/backend/alembic/versions/20260802_0101_add_agent_memory_and_search_trace.py:14-16` 直接依赖 `20260725_0100`。把该文件复制到最新主仓库会形成断裂分支或无法解析的 parent。

正确做法：

1. 在最新 `main` 数据库迁移到 `8c314438f8b1`。
2. 以该 head 新建迁移。
3. 创建 `session_kind`、记忆和审计表。
4. 去掉 `properties.id` 外键，改为 UnitType/Institute。
5. 在 PostgreSQL 和 SQLite 测试元数据中分别验证 JSONB fallback。

### 8.6 最新主仓库测试元数据已损坏

`[MAIN]/backend/app/models/embedding_job.py:21-23` 仍声明：

```text
embedding_jobs.property_id → properties.id
```

而 `[MAIN]/backend/app/db/base.py:1-24` 导入的元数据中没有 `properties` 表。`[MAIN]/backend/tests/conftest.py:34-45` 在每个测试前调用 `Base.metadata.create_all()`，因此 SQLAlchemy 在创建任何表之前就抛出 `NoReferencedTableError`。

这解释了为什么主仓库 Agent 测试 10 个全部 error：失败点不是聊天回答断言，而是 fixture 建表。

### 8.7 UnitType 的职责和库存来源不同

最新主仓库 `[MAIN]/backend/app/models/unit_type.py:42-102` 把 UnitType 定义为最终可租实体，包含 `total_count/available_count/has_vacancy`，不再有 `rooms` 关系。`property_service.py:323-387` 直接返回 UnitType 库存。

当前工作区的 UnitType 仍是户型模板，库存来自对 Room 的聚合；`[WORK]/backend/app/services/property_service.py:389-397,487-492` 会统计 available Room 并要求数量大于零，同时保存代表 Room ID。

迁移时必须：

- 用 `UnitType.available_count` 代替 Room count。
- 删除“取最小 Room.id 作为代表”的逻辑。
- 用 `has_vacancy` 或 `available_count > 0` 过滤。

主仓库当前 `property_service.py:341-348` 只过滤 UnitType status，没有可靠过滤零库存；可能返回状态仍 available、但 `available_count=0` 的户型。这应作为基线修复。

### 8.8 Institute 新字段是可利用的数据资产

最新主仓库 `[MAIN]/backend/app/models/institute.py:27-52` 比当前多出街道、邮编、网站、建筑类型、总楼层、建成年份、单元总数、电梯、楼管 ID/微信/二维码等字段。

这些字段可以增强结构化筛选和回答，例如“有电梯的高层公寓”“较新的建筑”“联系楼管”。当前记忆和 retrieval 尚未完整利用它们。迁移时应把有明确产品价值且可公开的字段加入候选 facts，而不要把楼管私人联系信息直接塞进 LLM 上下文。

### 8.9 embedding 类型必须在迁移前定稿

最新主仓库的 `UnitType.embedding` 是 Text；当前是 pgvector `Vector(1536)`。如果不先定稿，模型迁移、HNSW DDL、脚本和检索代码会反复改动。

推荐目标：UnitType 使用 `Vector(1536)`，只为 `unit_types` 创建 HNSW cosine 索引；不再为已删除的 `properties` 建索引。富 embedding 文本应包含可验证的 Institute、POI、safety 和 commute 事实，但删除无来源人群画像。

---

## 9. 前端逐能力差异

### 9.1 实际可达路由

| 页面/组件 | 最新主仓库 | 当前工作区 | 可达性结论 |
|---|---|---|---|
| `/ai-search` → `AiSearch.vue` | 有，无显式登录门禁 | 有，`requiresAuth=true` | 两边都可达，当前更完整 |
| `/search` → `Search.vue` | 有 | 有，并可打开右侧 Agent | 当前第二个真实 Agent 入口 |
| `/compare` | 组件存在但无路由 | 新增路由 | 可直达，但正常导航链仍不完整 |
| `SmartRentView.vue` | 无路由 | 无路由 | 不可达 |
| `AgentView.vue` | 无路由 | 无路由 | 不可达 |
| `ChatView.vue` | 无路由 | 无路由 | 不可达 |
| `AssistantBubble.vue` | 未挂载 | 未挂载 | 不可达 |

这一步非常重要：不能因为文件中写了来源 chips 或“深度模式”，就断言线上用户能看到。路由和 import 搜索确认，上述四个文件都没有实际消费者。

### 9.2 `/ai-search`：从演示页变成 Agent 工作台

主仓库 `AiSearch.vue` 224 行：

- 每次挂载新建会话。
- 消息只存在页面本地。
- 组件内手写 SSE 解析。
- 最多显示 6 张普通 PropertyCard。
- 无历史、长期记忆、FAQ、勾选比较。

当前 `AiSearch.vue` 727 行：

- 会话历史、新对话和切换：`[WORK]/frontend/src/views/AiSearch.vue:10-31`。
- 长期记忆展示与清空：`:33-51`。
- 固定 starter prompts：`:79-89,273-278`。
- 推荐卡在正文前展示：`:104-125`。
- 查询改写、状态和放宽：`:134-156`。
- FAQ 与站内链接：`:158-180`。
- 勾选至少两套后精确比较：`:184-190,491-499`。
- 20,000 字多行输入：`:192-221`。
- 公共 SSE Service：`:426-483`。
- 初始化时加载历史、记忆、购物车和 FAQ：`:544-567`。

缺口：`applyMeta()` 保存了 `sources`、`thinking_steps` 和 `aiAvailable`，但模板没有完整渲染来源、处理状态和 AI 降级提示。

### 9.3 Agent 推荐专用卡片

当前新增 `[WORK]/frontend/src/components/RecPropertyCard.vue`（398 行），集中展示：

- 图片、区域、价格、户型、面积和租期。
- 推荐理由。
- 后端真实设施。
- POI 距离。
- 对比勾选。
- 详情和候选清单操作。

相较主仓库普通 PropertyCard，它更适合解释“为什么推荐”。但币种缺失时直接回退人民币，没有完全复用统一币种工具。

### 9.4 `/search` 三栏联动

当前 `[WORK]/frontend/src/views/Search.vue` 从 1,095 行扩展到 1,344 行，并新增：

- Agent 开关：`:213-223`。
- 懒加载 `SearchAgentPanel.vue`：`:369`。
- 面板挂载：`:295-318`。
- 普通筛选转 `context_filters`：`:503-541`。
- 当前可见结果作为比较范围：`:777-780`。
- `filter_patch` 回填左侧筛选：`:789-931`。
- Agent 推荐同步中间列表：`:933-949`。
- 1100px 以下抽屉布局：`:1307-1326`。

这实现了“左侧普通筛选—中间结果—右侧 Agent”双向同步，是当前工作区最有价值的前端差异。

### 9.5 `SearchAgentPanel.vue`

当前独有 592 行：

- 当前条件 chips：`:18-23`。
- 固定提问和快捷操作：`:25-34,206`。
- 横向完整推荐卡：`:36-75`。
- 状态与渐进选项：`:81-94`。
- FAQ 和 20,000 字输入：`:129-160`。
- 创建/复用共享会话：`:229-244`。
- 使用 SSE 并传 `context_filters`：`:293-315`。
- 应用 `filter_patch`、同步推荐：`:318-322`。
- 精确传全部当前可见结果 ID：`:336-347`。

面板会接收 `query_rewrite/sources/ai_available`，见 `:349-366`，但模板没有把它们全部显示出来。

### 9.6 当前搜索页不能覆盖主仓库搜索页

主仓库 `Search.vue` 独有：

- 大学搜索模式：`[MAIN]/frontend/src/views/Search.vue:234-240`。
- 远程大学建议：`:247-268`。
- 1-20 km 半径。
- Google Maps 动态加载：`:211-227`。
- 大学标记、建筑详情和更完整 PropertyCard 操作。

当前版本删除了大学模式，改用 Leaflet，并在 `[WORK]/frontend/src/views/Search.vue:346-362` 使用浏览器端 `require()`。标准 Vite 浏览器环境通常没有 `require`；失败后 `initLeaflet()` 返回空值，后续仍调用 `.map()`，地图模式存在明显运行时风险。

所以正确方案是在主仓库 Search 页面**局部植入** Agent 面板与双向合同，保留主仓库地图和大学搜索。

### 9.7 前端 Agent Service

当前 `[WORK]/frontend/src/services/agent.ts` 新增会话、历史和记忆 API；SSE 客户端也更稳健：

- 从 localStorage 获取 token 并组装 Bearer：`:91-99`。
- 支持 `AbortSignal`：`:85-100`。
- 支持 CRLF 和多行 SSE data：`:117-150`。
- 支持 token/meta/error 回调和更清晰 HTTP 错误。

主仓库通过 `api.defaults.headers.common.Authorization` 获取 token，但实际 token 由 Axios 拦截器临时注入，SSE 请求可能漏认证。

当前权衡：Service 硬编码 `/api/v1`；页面虽然支持 AbortSignal，却没有在卸载时真正传入和中止。

### 9.8 Pinia Store

主仓库 Store 只有单一 sessionId、消息、AI 状态和 pendingQuery。当前 `[WORK]/frontend/src/stores/agentChat.ts` 新增：

- 会话列表、历史加载状态、长期偏好。
- 历史消息反序列化并恢复推荐卡/链接。
- 新建与切换会话。
- 保存、清空记忆。
- 登出时清理本地状态。

当前 `/ai-search` 和 Search 右侧面板共享同一个 Agent 会话，因此页面切换可以延续上下文。

限制：Store 忽略 `total/has_more`，不恢复 `thinking_steps/filter_patch`。

### 9.9 TypeScript 合同

当前 `frontend/src/types/agent.ts` 从 136 行扩展到 273 行，增加会话、历史、记忆、扩展筛选、GuidedOption、来源、Rewrite、状态、指代、流式 meta、评分和历史消息字段。

这使前端能够使用当前后端新增能力，但它引用的是当前版 `PropertyType`。最新主仓库的枚举是 `studio/ensuite/1bed/2bed/...`，当前是 `studio/1-bed/2-bed/shared/house`；直接复制会产生请求值和编译冲突。

### 9.10 详情路由与 ID 语义

最新主仓库：

- `/building/:id` 是正式详情。
- `/room/:id` 走 `BuildingRedirect.vue`。
- `/property/:id` 重定向到 building。

当前工作区：

- `/property/:id`、`/room/:id` 都指向旧 `PropertyDetail.vue`。
- 删除 `/building/:id`。

Agent 推荐卡、候选清单和对比页面必须在迁移前统一跳转目标，否则同一个 ID 会被带到错误详情页。

### 9.11 未挂载代码造成的“纸面能力”

- `SmartRentView.vue` 当前确实实现来源 chips、处理过程、查询改写和分数，但没有路由。
- `AssistantBubble.vue` 当前退回非流式请求，而且没有被挂载。
- `CartView.vue` 的“帮我对比”只设置 `pendingQuery`；唯一监听者是未挂载气泡，因此没有可见反馈。
- `openWithQuery()` 没有已挂载消费者。

这些差异应标记为“不可达代码”，不能算已交付功能。

---

## 10. 测试证据

### 10.1 当前工作区

执行：

```text
tests/test_agent.py
tests/test_agent_filter_patch.py
tests/test_agent_intelligence.py
tests/test_agent_user_scenarios.py
```

结果：

```text
31 passed, 1 warning
```

覆盖了基础 Agent、filter patch、记忆/检索智能和典型用户场景。这说明当前增强在当前旧模型测试环境中是连贯的。

### 10.2 最新主仓库

执行 `tests/test_agent.py`，结果是 10 个 error。共同根因：

```text
NoReferencedTableError:
embedding_jobs.property_id cannot find table properties
```

因此主仓库当前 Agent 测试基线不可用。必须先修复模型元数据，才能继续判断 Cart、Search、Compare 具体逻辑是否通过。

### 10.3 前端测试空白

两边都没有为下列 Agent 交互新增 Vitest：

- AiSearch 多会话。
- SearchAgentPanel。
- filter patch 双向同步。
- SSE parser。
- 历史回放。
- 长期记忆。
- 当前可见结果比较。
- 登录跳转。

当前主要依赖后端 pytest、人工浏览器验收和文档记录。迁移后必须补自动测试，否则最容易在模型适配时出现“页面能打开，但筛选字段/ID 已错位”的回归。

### 10.4 手工 HTML 联调页

当前独有 `[WORK]/backend/test/TEST_GUIDED_SEARCH.html`，可以登录、提问、检查 guided options、购物车和对比，但它已经部分过时：

- 使用非流式端点。
- 检查旧 `_poi_score/_poi_distances` 字段。
- 对比读取 `properties/results`，当前正式响应是 `items`。
- 价格硬编码人民币。

它可以保留为人工工具，但不能作为自动验收真源。

### 10.5 数据脚本也分属两套模型

当前独有 `backend/scripts/seed_agent_demo.py` 会创建 NUS、UCL、UCLA、HKU 四个市场，每个市场创建 Institute、UnitType 和两间 Room，并覆盖 SGD/GBP/USD/HKD。它适合当前 Room 模型，但：

- 不生成 embedding、POI 或 commute。
- 内置并打印固定演示账号密码。
- 迁移到 roomless 主仓库后无法原样使用。

主仓库独有或更匹配新模型的脚本包括：

- `build_rag_embeddings.py`
- `compute_safety_scores.py`
- `precompute_commutes.py`
- `seed_v3_test_data.py`

它们围绕 InstitutePOI、InstituteCommute 和 UnitType 库存。最终应重写 demo seed：直接创建 UnitType 库存、从环境变量读取演示凭据，并在 seed 后生成 embedding、POI 和通勤测试数据。

### 10.6 对比中的汇率只是近似数据

当前 CompareAgent 能正确保留原始币种展示，并在跨币种评分时换算为 CNY；相较主仓库硬编码人民币更合理。但 `[WORK]/backend/app/services/currency.py:15-21` 使用静态汇率，没有数据来源、更新时间、自动刷新或历史快照。

它适合演示和近似排序，不适合作为金融级结算依据。最终 UI 应明确“仅用于比较”，租金展示始终以房源原币种为准。

---

## 11. 文档差异与时效性

### 11.1 当前工作区独有文档

| 文档 | 行数 | 价值 | 主要时效问题 |
|---|---:|---|---|
| `docs/agent-interaction-rag-upgrade-report.md` | 437 | 解释记忆、Rewrite、检索、Grounding、SSE | 声称来源已展示，但可达页面未完整渲染 |
| `docs/agent-search-memory-fix-verification.md` | 197 | 阶段修复记录 | “前 5 套”比较已过时 |
| `docs/agent-search-memory-interaction-validation-report.md` | 359 | 最接近最终用户验收 | 隔离库通过不等于最新 main 可迁移 |
| `docs/search-agent-three-panel-merge-guide.md` | 580 | 三栏字段映射和布局说明 | 非流式、不传结果 ID 等描述已被代码反转 |
| `docs/recent-change-summary-20260727-20260804.md` | 548 | 最完整状态和限制汇总 | 比较基线仍是旧 `main@2e48d05` |

### 11.2 两边相同但已经陈旧的架构文档

两边相同的 `backend/AI_SCENARIOS.md`、`backend/AGENT_REFACTOR_CHECKLIST.md`、`docs/agent-architecture/**` 等不是差异，但内容仍以 Discovery/Compare/Cart、ReAct/Handoff 或多模式为中心。

当前实际主链已由 Dispatcher + Query Understanding + Memory + Retrieval 驱动，SearchAgentPanel 还可以直接把当前结果 ID 传给 Agent。旧图应标注为“历史/目标架构”，并新增“当前实际执行链”。

### 11.3 最可信的文档顺序

若要理解当前工作区，应按以下优先级阅读：

1. 本报告：使用最新主仓库快照重新比较。
2. `agent-search-memory-interaction-validation-report.md`：最终交互行为。
3. `recent-change-summary-20260727-20260804.md`：已知限制和未提交状态。
4. `agent-interaction-rag-upgrade-report.md`：智能链路设计。
5. 其他阶段文档：仅作历史记录。

---

## 12. 逐文件差异索引

### 12.1 编码助手与协作配置

该范围内没有跨仓库不同文件。以下路径全部相同：

- `AGENTS.md`
- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/launch.json`
- `.claude/skills/**`
- `.qoder/**`
- `.mcp/**`
- `uhomes-design/**`
- `.github/**`
- `.gitignore`
- `README.md`

它们的共同缺陷已在第 4 章逐项解释。

### 12.2 后端核心差异文件

| 文件 | 差异类型 | 解释 |
|---|---|---|
| `backend/.env.example` | 当前修改 | 新增 6 个 Agent 记忆/检索/上下文参数 |
| `backend/app/core/config.py` | 当前修改 | 对应参数、范围与默认值 |
| `backend/app/api/v1/routes/agent.py` | 大幅修改 | 会话列表、历史、记忆、扩展响应、流式 meta |
| `backend/app/schemas/agent.py` | 大幅修改 | 20+ 筛选字段和可解释结果合同 |
| `backend/app/models/agent_intelligence.py` | 当前新增 | 4 张记忆/搜索审计模型 |
| `backend/app/models/chat.py` | 当前修改 | 增加 `session_kind` 区分普通聊天与 Agent |
| `backend/app/services/chat_service.py` | 当前修改 | 创建/读取 Agent 会话并持久化元数据 |
| `backend/app/services/agentic/context.py` | 当前新增 | 历史与 grounded 候选打包 |
| `backend/app/services/agentic/memory.py` | 当前新增 | 状态、长期记忆、指代、审计 |
| `backend/app/services/agentic/query_understanding.py` | 当前新增 | Rewrite 和规则降级 |
| `backend/app/services/agentic/retrieval.py` | 当前新增 | 消融、重排和来源 |
| `backend/app/services/agentic/guided_search.py` | 当前新增 | POI 软排序和引导 chip，但依赖旧 Room |
| `backend/app/services/agentic/dispatcher.py` | 大幅修改 | 新主链、状态步骤、真流式和持久化 |
| `backend/app/services/agentic/agents/search_agent.py` | 大幅修改 | 统一候选、放宽、重排、Grounding、SSE |
| `backend/app/services/agentic/agents/compare_agent.py` | 修改 | 币种、评分和可解释对比 |
| `backend/app/services/agentic/shared.py` | 修改 | 真实币种/设施及分析辅助 |
| `backend/app/services/agentic/orchestration/supervisor.py` | 小幅修改 | 兼容新上下文/步骤 |
| `backend/app/services/agentic/orchestration/tool_registry.py` | 小幅修改 | 工具参数适配 |
| `backend/app/services/llm_service.py` | 当前修改 | 流式和调用参数配合 |
| `backend/alembic/...20260802_0101...py` | 当前新增 | 记忆与搜索审计迁移，但 parent 不兼容 main |
| `backend/tests/test_agent.py` | 当前修改 | 适配增强合同 |
| `backend/tests/test_agent_filter_patch.py` | 当前新增 | 筛选补丁 |
| `backend/tests/test_agent_intelligence.py` | 当前新增 | 记忆、理解、检索 |
| `backend/tests/test_agent_user_scenarios.py` | 当前新增 | 用户场景 |

### 12.3 前端核心差异文件

| 文件 | 差异类型 | 解释 |
|---|---|---|
| `frontend/src/views/AiSearch.vue` | 大幅修改 | 多会话、记忆、FAQ、SSE、完整卡片、比较 |
| `frontend/src/components/RecPropertyCard.vue` | 当前新增 | Agent 推荐专用卡片 |
| `frontend/src/views/Search.vue` | 大幅分叉 | 当前加三栏；主仓库加大学地图和建筑体验 |
| `frontend/src/components/search/SearchAgentPanel.vue` | 当前新增 | 三栏右侧 Agent 核心 |
| `frontend/src/services/agent.ts` | 修改 | 会话/记忆 API 和稳健 SSE |
| `frontend/src/stores/agentChat.ts` | 大幅修改 | 多会话、历史和长期记忆状态 |
| `frontend/src/types/agent.ts` | 大幅修改 | 扩展合同 |
| `frontend/src/router/index.ts` | 修改 | `/ai-search` 登录门禁、`/compare` |
| `frontend/src/views/SmartRentView.vue` | 修改但不可达 | 来源、Rewrite、分数等纸面 UI |
| `frontend/src/components/AssistantBubble.vue` | 修改但不可达 | 登录限制、非流式回退 |
| `frontend/src/utils/currency.ts` | 当前新增 | 多币种格式化，但未完全统一采用 |
| `frontend/src/types/property.ts` | 高冲突修改 | Property 与 UnitType 枚举/字段分叉 |
| `frontend/src/services/property.ts` | 高冲突修改 | `/properties` 与 `/unit-types/buildings` 分叉 |
| `frontend/src/components/SmartSearch.vue` | 高冲突修改 | 当前删大学搜索，主仓库保留 |
| `frontend/src/layouts/DefaultLayout.vue` | 高冲突修改 | 导航入口和角色可见性不同 |
| `frontend/src/components/PropertyCard.vue` | 高冲突修改 | 卡片实体和详情路由不同 |

### 12.4 最新主仓库中必须保留并适配的文件

- `backend/app/models/unit_type.py`
- `backend/app/models/institute.py`
- `backend/app/models/poi.py`
- `backend/app/models/institute_commute.py`
- `frontend/src/views/BuildingDetail.vue`
- `frontend/src/views/BuildingRedirect.vue`
- `frontend/src/components/GoogleMap.vue`
- `frontend/src/services/building.ts`
- 最新版 `frontend/src/views/Search.vue`
- 最新版 `frontend/src/components/SmartSearch.vue`

---

## 13. 风险分级

### 13.1 P0：不先处理就不能合并

1. **AgentCart ID 合同断裂。** Model 用 `unit_type_id`，Service/API 用 `property_id`。
2. **主仓库 Base metadata 无法建表。** `EmbeddingJob` 外键指向不存在的 `properties`。
3. **推荐 ID 语义未统一。** Room/Property/UnitType/Institute 在不同层混用。
4. **POI 与通勤 join 使用已删除 Room。** 当前实现不能落在最新模型。
5. **Alembic parent 不存在。** 当前记忆迁移不能复制到主仓库。
6. **整文件覆盖 Search/Property 类型会回退主仓库功能。** 大学搜索、Google Maps、建筑详情会被删除。
7. **当前核心新增模块未跟踪。** 若漏提交 `memory/context/query_understanding/retrieval`，服务会在 import 阶段失败。
8. **主仓库 Compare/ToolRegistry/Supervisor 仍使用旧 Property 字段。** 只修购物车模型不足以恢复完整 Agent。

### 13.2 P1：迁移后上线前必须完成

1. 在可达页面真正显示来源、查询改写和 AI 降级状态。
2. 为会话列表和历史接入分页。
3. 为 SSE parser、filter patch、历史/记忆和当前结果比较增加前端测试。
4. 页面卸载时使用 AbortController 中止 SSE。
5. 更新或废弃过时 HTML 联调页和阶段文档。
6. 统一币种工具，移除默认人民币的隐式假设。
7. 修复当前 Leaflet `require()`；若以 main 为底座则直接保留 Google Maps。
8. 明确 `mode=expert/handoff` 的兼容策略，删除不可达旧模式或重新接通。
9. 决定 Text 与 pgvector embedding 的最终存储，并声明 numpy/pgvector 依赖。
10. 增加记忆 TTL、告知、脱敏、并发 upsert 和审计清理策略。
11. 优化会话列表聚合查询，按准确 message ID 更新历史 metadata。
12. 修复主仓库零库存 UnitType 仍可能被搜索返回的问题。

### 13.3 P2：协作与长期维护

1. 重建 `AGENTS.md`、`CLAUDE.md` 乱码段，并指定唯一权威规则。
2. 收紧 `.claude/settings.json`。
3. 修复/删除失效 Gitlink 和不存在的 `skills.json`。
4. 解决 5px/16px、字体和 `--accent` 冲突。
5. 恢复必要截图/字体或移除无法履行的设计要求。
6. 重新生成 Qoder RepoWiki。
7. 在 README 中增加 AI 协作配置入口。

---

## 14. 推荐迁移方案

### 阶段 0：冻结证据与保护现有成果

1. 保留本次主仓库干净克隆作为审计快照。
2. 将当前未提交 Agent 修改拆成可审查提交，避免只存在本机工作树。
3. 保存当前 31 项通过的测试输出和关键浏览器截图。
4. 不在当前分支上直接 merge 最新 main 后边改边猜。

### 阶段 1：从最新 `main` 创建迁移分支

以 `[MAIN]@78de6ec` 为底座创建新功能分支。该分支继承最新数据模型、地图、详情、权限和业务修复。

### 阶段 2：先修主仓库基线

1. 将 `EmbeddingJob` 改到 UnitType，或删除已废弃模型。
2. 统一 `AgentCartItem`、CartService、API、Schema 为 UnitType。
3. 同步修复 CompareAgent、ToolRegistry、Supervisor 和 shared helper 的旧字段。
4. 修复 SearchAgent 对已删除 RoomCommute 的引用，并过滤零库存 UnitType。
5. 运行 Base metadata create/drop 和现有 Agent 测试，确保主仓库基线恢复为绿色。

### 阶段 3：确定唯一实体合同

建议：

- 推荐主键：`unit_type_id`。
- 建筑上下文：`institute_id`。
- 详情链接：`/building/:institute_id`，可带 `unit_type_id` 选中户型。
- 候选清单和对比：存 `unit_type_id`。
- API 过渡期可返回 `property_id` 兼容别名，但必须文档化为 UnitType ID，随后废弃。

### 阶段 4：重建数据库迁移

从 `8c314438f8b1` 新建一个 Agent intelligence revision：

- `chat_sessions.session_kind`
- `agent_session_states`
- `agent_user_memories`
- `agent_search_runs`
- `agent_search_candidates`

候选表只引用 `unit_types`，可选引用 `institutes`；不再引用 `properties`。

### 阶段 5：移植纯智能模块

优先移植相对独立的：

- `memory.py`
- `query_understanding.py`
- `retrieval.py`
- `context.py`

把所有 `property_id` 命名和旧模型 fallback 改成目标合同。先做单元测试，再接 SearchAgent。

### 阶段 6：适配检索、POI 与通勤

1. 候选池直接以 UnitType 为单位。
2. POI：`UnitType.institute_id → InstitutePOI`。
3. 通勤：`UnitType.institute_id → InstituteCommute`。
4. embedding 文本保留主仓库新增的社区、POI、安全和建筑信息。
5. 将当前 constraint ablation、reranker、source manifest 和 grounding 接到这套新候选结构。
6. 删除 Room/Property fallback，而不是继续叠兼容层。

### 阶段 7：移植 API 和历史能力

移植会话列表、历史、记忆和扩展 response；使用新的 UnitType recommendation DTO。为同步与 SSE 端点写相同的契约测试，保证最终 meta 字段一致。

### 阶段 8：在主仓库前端做局部植入

1. 保留主仓库 `Search.vue`、大学半径搜索、Google Maps、BuildingDetail。
2. 植入 `SearchAgentPanel.vue`、开关、context filters、filter patch 和推荐同步。
3. 把当前 AiSearch 的会话/记忆/SSE/比较交互迁入，但卡片适配 UnitType/Institute。
4. 更新 `types/agent.ts`，不要覆盖主仓库 `types/property.ts`。
5. 所有详情链接统一到目标路由。

### 阶段 9：补测试和可观测性

- 后端：模型建表、迁移、记忆隔离、指代、放宽、排序、来源、购物车、对比、SSE。
- 前端：Service SSE parser、Store、AiSearch、SearchAgentPanel、filter patch、路由登录、Abort。
- E2E：大学搜索 + Agent、地图模式 + Agent、跨会话记忆、至少两套对比、零结果放宽。

### 阶段 10：更新文档与协作配置

1. 写一份“当前实际 Agent 执行链”。
2. 将早期三栏指南标记过时或更新。
3. 修复 AGENTS/CLAUDE 乱码和权限问题。
4. 更新 Qoder 快照。

---

## 15. 验收清单

### 15.1 数据与迁移

- [ ] `alembic heads` 只有一个 head，基于最新 main。
- [ ] 全新 PostgreSQL 可 `upgrade head`。
- [ ] 已有数据库可无损升级。
- [ ] SQLite 测试 metadata 可 create/drop。
- [ ] 不存在指向 `properties.id` 的孤立外键。
- [ ] AgentCart 全链路只使用统一 ID。

### 15.2 后端 Agent

- [ ] 新会话、会话列表、历史回放工作。
- [ ] 长期记忆读/写/清空按用户隔离。
- [ ] “第二套/最便宜的/这个”解析正确。
- [ ] 零结果只做最小约束放宽，并返回轨迹。
- [ ] 排名分数可重复、可解释。
- [ ] POI 来自 InstitutePOI。
- [ ] 通勤来自 InstituteCommute。
- [ ] 缺失数据不会被 LLM 猜测。
- [ ] 同步与 SSE 返回同样的结构化结果。
- [ ] 购物车和对比不会错用 ID。

### 15.3 前端

- [ ] `/ai-search` 可切换会话并恢复卡片。
- [ ] `/search` 保留大学半径搜索和 Google Maps。
- [ ] Agent 面板可将当前筛选发给后端。
- [ ] filter patch 能安全回填，未知值不会破坏筛选器。
- [ ] 推荐同步到中间列表但不破坏分页/地图。
- [ ] 可精确比较当前全部可见结果。
- [ ] 来源、Rewrite、放宽和 AI 降级状态对用户可见。
- [ ] 页面卸载会中止 SSE。
- [ ] 所有详情链接指向正确 Building/UnitType。
- [ ] 多币种无默认人民币误导。

### 15.4 回归与文档

- [ ] 当前 31 个后端测试迁移到新模型后继续通过。
- [ ] 主仓库原 Agent 测试不再在 fixture 阶段报错。
- [ ] 新增 Agent 前端 Vitest 与关键 E2E。
- [ ] 过时指南已更新或标记历史。
- [ ] AGENTS/CLAUDE 乱码修复。
- [ ] Claude 默认权限经过最小化审查。

---

## 16. 不建议采用的合并方式

### 16.1 不要直接 merge 当前工作树

当前工作树跨 38 个已跟踪修改和 26 个未跟踪条目，同时最新 main 又有 97 个后续提交。直接合并会把业务模型冲突、功能回退和 Agent 增强混在同一次冲突处理中，难以审查。

### 16.2 不要整文件复制 `Search.vue`

这样会获得三栏 Agent，但丢失大学建议、半径搜索、Google Maps、完整 PropertyCard 和建筑详情体验。

### 16.3 不要直接复制当前 Alembic 文件

其 parent 在主仓库迁移图中不存在，且表中保留 `properties.id` 外键。

### 16.4 不要继续扩大兼容别名

`Property = UnitType`、`Room = UnitType`、API 字段仍叫 `property_id` 会让代码看似能 import，实际语义越来越模糊。应明确目标模型并逐步删除兼容层。

### 16.5 不要把“文件存在”当“功能已交付”

SmartRent、AgentView、ChatView、AssistantBubble 中的部分增强当前不可达；验收必须从路由和真实用户路径出发。

---

## 17. 最终建议

主仓库和当前工作区不是“新旧两个完整版本”，而是两条分别进化的支线：

- 最新 `main` 是更合适的**业务与数据底座**。
- 当前工作区是更成熟的**Agent 智能与交互能力来源**。

最稳妥的技术决策是：**从最新 main 新开分支，先修主仓库 P0 基线，再按模块移植当前 Agent，并彻底适配 Institute/UnitType。**

如果按这个顺序执行，可以同时保住：

- 主仓库的新房源模型、大学搜索、Google Maps 和建筑详情。
- 当前工作区的长期记忆、查询理解、混合检索、可解释排序、Grounding、真流式和三栏 Agent。

如果直接 merge、cherry-pick 大文件或复制迁移，则最可能出现三类结果：数据库迁移断裂、推荐/购物车 ID 指错对象，以及主仓库现有搜索体验被回退。

---

## 附录 A：关键证据摘要

| 证据 | 结果 |
|---|---|
| 主仓库 HEAD | `78de6ec93ff9120574a36c50488b3be74ef300f1` |
| 当前分支 HEAD | `3f0bee15dec28681fcb1f873585090fd587137ea` |
| 共同基线 | `2e48d05a743030c0ac67ccdab7e7faf5d29182e8` |
| 基线后提交 | 当前 5；main 97 |
| 协作配置核验 | 309 个条目，零差异 |
| Agent 服务规模 | main 22 文件/6,403 行；当前 27 文件/9,332 行 |
| Alembic | main 88 个文件/head `8c314438f8b1`；当前 74 个/head `20260802_0101` |
| 当前 Agent 测试 | 31 passed, 1 warning |
| main Agent 测试 | 10 errors，建表外键阻断 |

## 附录 B：术语约定

- **编码助手 Agent：** Codex、Claude Code、Qoder、Skills、MCP 和 GitHub 协作规则。
- **产品 Agent：** 面向租客的 AI 找房、推荐、对比、候选清单和搜索助手。
- **Property/Room：** 当前工作区中 `properties` 表的可租房间实体。
- **Institute：** 最新主仓库中的公寓/建筑实体。
- **UnitType：** 最新主仓库中的户型/可推荐核心实体。
- **Grounded Answer：** 只基于已打包并标注来源的候选事实生成回答。
- **Constraint Ablation：** 逐个试验放宽条件，以最小改变恢复结果。
- **SSE：** Server-Sent Events，服务端持续向浏览器推送 token 和最终结构化结果。

## 附录 C：合并前必须由团队确认的三项产品决策

1. 推荐、购物车和对比的唯一 ID 是否正式定为 `unit_type_id`。
2. 点击推荐卡后是进入 Building 详情并选中户型，还是新增 UnitType 独立详情页。
3. 长期记忆是默认自动积累，还是仅保存用户显式确认的偏好；当前实现偏向“稳定字段可积累 + 用户可显式保存/清空”，需要产品和隐私口径一致。

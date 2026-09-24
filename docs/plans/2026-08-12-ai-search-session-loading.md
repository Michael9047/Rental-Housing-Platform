# AI 搜索会话加载实现计划

**目标：** 每次提交普通搜索时绑定一个干净的 AI 会话，但不发送 AI 消息；已有空会话时直接复用；搜索框保留用户实际输入；左侧人工筛选与当前对话提取条件共同限制结果。

**架构：** 普通搜索导航使用 `q` 原样携带用户输入，并增加唯一的 `search_id` 表示一次新的提交事件。搜索结果页消费该事件后，通过共享 Pinia store 复用当前空会话或创建新会话。人工筛选与对话筛选分别保存，只在请求结果时合并。

**技术栈：** Vue 3、TypeScript、Pinia、Vue Router、Vitest、Element Plus。

---

### 任务一：复用空会话

**涉及文件：**

- 修改：`frontend/src/stores/agentChat.ts`
- 测试：`frontend/src/stores/__tests__/agentChat.test.ts`

**步骤：**

1. 测试当前会话只有欢迎语时直接复用，已有真实消息时创建新会话。
2. 增加 `prepareForSearch()`，检查当前消息和服务端最近会话摘要。
3. 运行对应 store 测试。

### 任务二：保留搜索文字并识别普通搜索事件

**涉及文件：**

- 修改：`frontend/src/components/HomeSearchBox.vue`
- 修改：`frontend/src/layouts/DefaultLayout.vue`
- 修改：`frontend/src/views/Search.vue`
- 新增：`frontend/src/utils/normalSearch.ts`
- 测试：`frontend/src/__tests__/normalSearch.test.ts`

**步骤：**

1. 所有普通搜索导航都让 `q` 原样保存用户输入，并增加唯一的 `search_id`。
2. 删除普通搜索将文字排队为 AI 消息的调用。
3. 顶部搜索框只从 `route.query.q` 同步，刷新后仍显示本次输入。
4. 搜索页每个 `search_id` 只处理一次：准备空会话、清理上次对话条件、打开管家，但不发送消息。

### 任务三：拆分人工筛选与对话筛选

**涉及文件：**

- 修改：`frontend/src/views/Search.vue`
- 修改：`frontend/src/components/search/SearchAgentPanel.vue`
- 测试：`frontend/src/components/search/__tests__/SearchAgentPanel.test.ts`

**步骤：**

1. 现有左侧状态继续作为人工筛选，新增独立的对话筛选状态。
2. AI 返回的筛选补丁只更新对话筛选，不回写左侧控件。
3. 请求结果时合并两层条件。
4. 左侧条件调整或重置只刷新结果，不创建或清除 AI 会话。
5. 新建对话时清除旧对话条件，但保留左侧人工条件。
6. 运行组件和 store 定向测试、类型诊断与 `git diff --check`。

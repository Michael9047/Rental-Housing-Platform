# AI 对话搜索工作区与游客历史认领 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让每个 AI 对话持久绑定一份可恢复的搜索工作区，并允许游客使用全页 AI、在登录后将游客对话认领到正式账号。

**Architecture:** `chat_sessions` 作为对话与搜索工作区的一对一权威实体，新增唯一 `search_id` 与 JSON 搜索工作区。搜索页通过 `search_id` 恢复原会话、人工筛选和 UI 状态；AI 条件继续以会话的 `accumulated_filters` 为权威来源。游客使用 `guest_token` 访问同一组接口，正式登录后通过显式认领接口把 guest 会话迁移到当前用户。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、PostgreSQL/SQLite tests、Vue 3、Pinia、Vue Router、Vitest。

---

### Task 1: 对话搜索工作区数据模型与 API

**Files:**
- Modify: `backend/app/models/chat.py`
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/api/v1/routes/agent.py`
- Create: `backend/alembic/versions/20260812_0041_add_agent_search_workspace.py`
- Test: `backend/tests/test_agent.py`

**Steps:**
1. 添加 API 测试，覆盖保存工作区、按 `search_id` 恢复、所有权隔离以及会话列表返回绑定状态。
2. 为 `ChatSession` 增加 `search_id` 和 `search_workspace`。
3. 增加工作区 PUT/GET schema 与路由，并在响应中返回会话累计 AI 条件。
4. 生成以当前 Alembic head 为父节点的迁移。
5. 运行定向 pytest。

### Task 2: 游客身份统一与登录后认领

**Files:**
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/api/v1/routes/agent.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/services/agent.ts`
- Modify: `frontend/src/stores/agentChat.ts`
- Modify: `frontend/src/stores/auth.ts`
- Test: `backend/tests/test_agent.py`
- Test: `frontend/src/stores/__tests__/agentChat.test.ts`

**Steps:**
1. 添加游客创建、携带 guest token 恢复历史以及登录用户认领 guest 会话的测试。
2. 普通 API 与流式 API 都采用 `access_token || guest_token`。
3. store 在所有创建会话路径统一保存后端返回的 `guest_token`。
4. 增加仅登录用户可调用的认领接口，验证 guest token 后迁移其 Agent 会话。
5. 所有登录方式在设置正式 token 后执行认领，并刷新当前 Agent 状态。
6. 运行后端与 store 定向测试。

### Task 3: 搜索页双向恢复

**Files:**
- Modify: `frontend/src/types/agent.ts`
- Modify: `frontend/src/services/agent.ts`
- Modify: `frontend/src/stores/agentChat.ts`
- Modify: `frontend/src/views/Search.vue`
- Modify: `frontend/src/components/search/SearchAgentPanel.vue`
- Test: `frontend/src/stores/__tests__/agentChat.test.ts`

**Steps:**
1. 新搜索先按 `search_id` 查询绑定；存在则切换原会话，不存在才准备空会话。
2. 将顶部查询、左侧人工筛选、学校/半径及排序保存到当前会话工作区。
3. 搜索页刷新、详情返回、全页 AI 返回时恢复同一个会话及左右约束。
4. 打开全页 AI 前强制保存当前工作区。
5. 验证浏览器历史中的 A/B 搜索分别恢复对应会话。

### Task 4: 游客全页 AI 与从对话返回搜索

**Files:**
- Modify: `frontend/src/views/AiSearch.vue`
- Modify: `frontend/src/stores/agentChat.ts`
- Test: relevant frontend tests

**Steps:**
1. 移除全页 AI 的登录重定向；无 token 时先创建 guest 会话，再加载历史。
2. 在当前对话提供“查看搜索结果”动作。
3. 已绑定工作区时导航到其 `search_id`；未绑定时以当前对话创建空人工条件工作区，再进入搜索页。
4. 切换历史对话后，按钮始终对应当前对话。
5. 运行定向 Vitest、相关文件类型检查和 `git diff --check`。

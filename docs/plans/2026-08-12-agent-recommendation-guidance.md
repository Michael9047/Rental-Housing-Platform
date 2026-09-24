# AI 推荐卡片滚轮与渐进对话指引 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复推荐卡片的鼠标滚轮翻页，并让 AI 根据真实结果数量按优先级引导用户收窄或放宽条件。

**Architecture:** 前端滚轮指令按完整卡片宽度离散翻页，并只在横向列表仍可滚动时阻止页面滚动。后端将分叉的引导规则统一到 `guided_search.py` 的纯决策函数，使用真实结果总数、有效筛选条件、约束消融轨迹和当前任务内已尝试层级生成最多一层放宽建议或若干缺失维度提示。

**Tech Stack:** Vue 3、TypeScript、Vitest、FastAPI、Python、pytest

---

### Task 1: 修复推荐列表鼠标滚轮翻页

**Files:**
- Modify: `frontend/src/directives/horizontalWheelScroll.ts`
- Test: `frontend/src/directives/__tests__/horizontalWheelScroll.test.ts`

**Steps:**
1. 增加失败测试，验证一次垂直滚轮至少翻过一张卡片，并在连续滚轮期间节流。
2. 将原始像素累加改为读取首张卡片宽度与列表间距后调用平滑 `scrollBy`。
3. 保留列表首尾释放页面滚动和触控板原生横向手势。
4. 运行 `npm test -- --run src/directives/__tests__/horizontalWheelScroll.test.ts`。

### Task 2: 统一结果数量驱动的对话指引

**Files:**
- Modify: `backend/app/services/agentic/guided_search.py`
- Modify: `backend/app/services/agentic/dispatcher.py`
- Test: `backend/tests/test_agent_guided_options.py`

**Steps:**
1. 为结果过多、数量合适、结果过少的决策树编写纯函数测试。
2. 定义 0–3 为过少、4–7 为合适、8 及以上为过多。
3. 过多时按户型、预算、通勤检查缺失维度；通勤缺目的地时先引导补学校。
4. 过少时严格按设施、周边、预算、户型返回当前第一条可执行放宽建议。
5. 使用 `relaxation_trace` 中的真实反事实数量生成更可靠的预算与放宽提示。
6. 删除 dispatcher 内旧 `_guided_options` 分叉并调用统一决策函数。

### Task 3: 记录同一找房任务的放宽进度

**Files:**
- Modify: `backend/app/services/agentic/dispatcher.py`
- Test: `backend/tests/test_agent_guided_options.py`

**Steps:**
1. 在 `accumulated_filters` 的内部键中保存已尝试放宽层级，不新增数据库字段。
2. 根据确定性的引导消息识别用户点击的层级；新找房任务自动清空进度。
3. 如果放宽后结果达到至少 4 个，不再返回后续放宽建议。
4. 如果仍为 0–3 个，跳到下一层而不重复刚才的层级。
5. 运行后端定向测试。

### Task 4: 回归验证

**Files:**
- Verify only

**Steps:**
1. 运行前端滚轮、推荐卡片和搜索面板测试。
2. 运行后端引导纯函数与 Agent 搜索相关测试。
3. 运行 Vite 生产打包和 `git diff --check`。
4. 如完整类型检查仍被工作区既有错误阻断，单独记录而不修改无关模块。

# CLAUDE.md — 租房平台 Claude Code 协作规范

> 本文件为 Claude Code 提供项目上下文与编码约定。与 AGENTS.md 内容一致，专为 Claude Code 优化。

---

## 分支命名

从 `main` 拉分支，格式：

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feat/<简述>` | `feat/amap-geocoding` |
| 修复 | `fix/<简述>` | `fix/property-image-upload` |
| 重构 | `refactor/<模块>` | `refactor/payment-service` |

全部小写英文，`-` 连接。个人临时分支加用户名前缀：`michael/feat/xxx`。

---

## Commit 规范

Conventional Commits，格式：`<type>(<scope>): <中文简述>`

type: `feat` / `fix` / `refactor` / `docs` / `style` / `test` / `chore`
scope: `backend` / `frontend` / `api` / `db` / `auth` / `map` / `payment` 等

---

## 项目结构

```
├── backend/                   # FastAPI 后端
│   ├── app/api/v1/routes/     # 路由层
│   ├── app/core/              # 配置、安全
│   ├── app/db/                # 数据库会话
│   ├── app/models/            # SQLAlchemy 模型
│   ├── app/schemas/           # Pydantic 模型
│   ├── app/services/          # 业务逻辑层
│   ├── app/tasks/             # Celery 异步任务
│   ├── tests/                 # pytest
│   └── alembic/               # 数据库迁移
├── frontend/                  # Vue 3 + TypeScript
│   └── src/
│       ├── components/ views/ router/ stores/ services/ types/
├── wechat-miniprogram/        # 微信小程序
└── docs/                      # 文档
```

---

## 代码风格

### 通用
- 注释和文档**必须使用中文**
- 变量、函数名用英文（Python: snake_case, TS: camelCase）
- 每个文件顶部一行注释说明用途
- **禁止提交 `console.log` / `print`**

### Python
- 类型标注贯穿始终（Pydantic + SQLAlchemy Mapped）
- `Decimal` 用于金额，`float` 仅用于比例
- 异步 IO 贯穿始终，async 函数中不写同步阻塞调用
- 新路由注册到 `backend/app/api/v1/router.py`

### TypeScript / Vue
- 使用 `<script setup lang="ts">`
- API 调用统一走 `frontend/src/services/`，不要在组件里 `fetch`
- Element Plus 组件优先，自定义样式用 `scoped` CSS

---

## 功能模块

| 模块 | 中文名 |
|------|--------|
| property | 房源管理 |
| booking | 预约看房 |
| payment | 支付系统 |
| contract | 电子合同 |
| auth | 认证授权 |
| chat | 在线沟通 |
| map | 地图服务 |
| poi | 周边设施 |
| notification | 消息通知 |
| images | 图片管理 |
| search | 智能搜索 |
| admin | 后台管理 |
| wechat | 微信集成 |

---

## Issue 与任务管理（Vibe Coding 模式）

### 工作流

```
vibe 开发 → 发 PR 时同时建 Issue → PR 链接 Issue → 合并后自动关闭
```

### 发 PR 时的完整流程

当你准备提交代码并发 PR 时，必须按以下顺序完成：

1. **创建 Issue**：根据 git diff 生成 Issue

   ```
   gh issue create \
     --title "[模块] 变更简述" \
     --body "## 变更概述
   ...（简单说明做了什么）

   ## 涉及文件
   - \`路径\` — 新增/修改/删除

   ## 技术要点
   ...

   ## 验收方式
   - [ ] pytest 通过
   - [ ] ..." \
     --label "模块标签,技术栈标签" \
     --assignee "@me"
   ```

2. **创建 PR**：遵循 `.github/PULL_REQUEST_TEMPLATE.md` 模板，描述中必须包含 `Closes #X`

3. **PR 描述中**：填写 AI 辅助声明、测试清单、数据库变更等 checklist

### Issue 标签规则
- 必须加对应模块标签 + `frontend` / `backend` / `wechat-miniprogram`
- 可加优先级标签：`high` / `medium` / `low`

---

## PR & Code Review

- PR 标题用中文：`[模块] 简述`
- 使用 `.github/PULL_REQUEST_TEMPLATE.md` 模板
- 描述中必须写 `Closes #X`
- 禁止 force push 到 `main`
- 合并前 CI 必须通过
- 合并后删除远程功能分支

### 关于截图（前端变更必填）
- **前端变更必须有运行截图**，后端/API 变更不需要
- Claude Code 无法截图 → 在 PR 描述中标注 `> ⚠ 截图待人工补充`，**PR 可以先提交但视为未完成**
- 开发者在本地浏览器验证后，必须在 review 前把截图补充到 PR 描述中
- 没有截图的 PR 不得通过 review

---

## 环境变量

- 敏感配置仅存 `.env`，不提交
- 新增环境变量同步更新 `.env.example`
- 前端变量以 `VITE_` 为前缀

---

## 数据库迁移

- 每次模型变更生成 Alembic 迁移：`alembic revision --autogenerate -m "简述"`
- 迁移文件名英文描述
- 禁止修改已合并的迁移文件

---

## 依赖管理

- 新增依赖前先确认未与现有依赖功能重叠
- 修改 `requirements.txt` 或 `package.json` 后在 PR 中说明原因
- 禁止随意引入新的第三方包，需要时可先问用户

---

## AI 行为准则

- 完成代码修改后，主动询问用户："需要我提交代码并发 PR 吗？"——不要自动推送
- 发 PR 时自动完成建 Issue + 填模板 + 关联 Issue 全流程
- 不要删除或修改已有测试，除非用户明确要求
- 不要自行升级依赖版本
- 遇到不确定的架构决策，先问用户而非自行决---

## ??????

- ??????????????????
- ??????? `git diff --check` ???????
- ??????????????? `npm run dev`??? `pytest`?

定
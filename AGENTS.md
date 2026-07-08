# AGENTS.md — 租房平台团队协作规范

> 本文档为项目中所有 AI 编码助手（Codex、Claude Code 等）提供统一的协作约定。人工开发者同样适用。

---

## 一、分支命名

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能开发 | `feat/<功能简述>` | `feat/amap-geocoding` |
| Bug 修复 | `fix/<问题简述>` | `fix/property-image-upload` |
| 重构 | `refactor/<模块名>` | `refactor/payment-service` |
| 文档 | `docs/<内容>` | `docs/api-guide` |
| 杂项 | `chore/<内容>` | `chore/update-deps` |
| 紧急修复 | `hotfix/<问题>` | `hotfix/login-crash` |

**规则：**
- 全部小写英文，单词用 `-` 连接
- 个人临时分支加用户名前缀：`michael/feat/xxx`
- 禁止直接用 `main` 做功能开发，始终从 `main` 拉分支

---

## 二、Commit 规范

采用 **Conventional Commits**，格式：

```
<type>(<scope>): <中文简述>

<详细说明（可选）>
```

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不改变功能） |
| `docs` | 文档 |
| `style` | 格式（空格、分号等，不影响逻辑） |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖 |

**scope 用模块名**：`backend`、`frontend`、`api`、`db`、`auth`、`map`、`payment` 等

**示例：**
```
feat(map): 接入高德地图地理编码，创建房源时自动回填经纬度
fix(payment): 修复微信支付回调签名校验失败的问题
chore(deps): 升级 cryptography 到最新版本
```

---

## 三、项目结构

```
Rental Housing Structure/
├── backend/                   # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/routes/     # 路由层（按功能分文件）
│   │   ├── core/              # 配置、安全、日志
│   │   ├── db/                # 数据库会话 & 迁移
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务逻辑层
│   │   └── tasks/             # Celery 异步任务
│   ├── scripts/               # 运维脚本（geocoding 补充等）
│   ├── tests/                 # pytest 测试
│   └── alembic/               # 数据库迁移
├── frontend/                  # Vue 3 + TypeScript 前端
│   └── src/
│       ├── components/        # 可复用组件
│       ├── views/             # 页面级组件
│       ├── router/            # 路由定义
│       ├── stores/            # Pinia 状态管理
│       ├── services/          # API 调用封装
│       └── types/             # TypeScript 类型定义
├── wechat-miniprogram/        # 微信小程序
├── docker/                    # Docker 配置
├── nginx/                     # Nginx 配置
├── docs/                      # 文档
└── docker-compose.yml         # 本地开发环境
```

---

## 四、代码风格

### 通用
- 注释和文档**必须使用中文**
- 变量、函数名使用英文小驼峰或下划线（遵循语言惯例）
- 每个模块/服务文件顶部写一行注释说明文件用途
- 不要提交调试用的 `console.log` / `print`

### Python（后端）
- 严格遵循项目已有的类型标注风格（Pydantic + SQLAlchemy Mapped）
- `Decimal` 用于金额，`float` 仅用于比例
- 新路由注册到 `backend/app/api/v1/router.py`
- 异步 IO 贯穿始终，不要在 async 函数中写同步阻塞调用

### TypeScript / Vue（前端）
- 使用 `<script setup lang="ts">` 语法
- API 调用统一走 `frontend/src/services/` 封装，不要在组件里直接 `fetch`
- Element Plus 组件优先，自定义样式用 `scoped` CSS

---

## 五、功能模块命名与描述

以下为项目各模块的中文标准命名，在 commit、PR、文档中统一使用：

| 模块 | 中文名 | 说明 |
|------|--------|------|
| property | 房源管理 | 房源 CRUD、搜索、状态管理 |
| booking | 预约看房 | 租客预约、房东确认 |
| payment | 支付系统 | 押金/租金支付、微信支付对接 |
| contract | 电子合同 | 租赁合同模板、签署 |
| auth | 认证授权 | 登录注册、RBAC 权限 |
| chat | 在线沟通 | 租客房东即时通讯 |
| map | 地图服务 | 高德地图、地理编码、周边搜索 |
| poi | 周边设施 | 房源周边 POI 数据 |
| notification | 消息通知 | 站内信、邮件、微信通知 |
| images | 图片管理 | 房源图片上传、缩略图 |
| search | 智能搜索 | pgvector 语义搜索 |
| admin | 后台管理 | 管理员面板 |
| wechat | 微信集成 | 小程序登录、微信支付 |

---


---

## 六、Issue 与任务管理（Vibe Coding 模式）

### 核心理念

本项目采用 **"先开发、后建 Issue"** 的 vibe coding 工作流：

```
传统流程：建 Issue → 认领 → 开发 → PR → 关 Issue
本组流程：vibe 开发 → 发 PR 时 AI 自动建 Issue → PR 链接 Issue → 合并后自动关
```

**为什么不提前建 Issue？**
- vibe coding 过程是探索性的，开发前不一定能准确描述最终产出
- 减少"建了 Issue 没人做"或"Issue 描述和实际代码不符"的问题
- Issue 的真正价值是**记录做了什么、为什么做**，而非分配任务

### Issue 生成规范

**触发时机**：每次发 PR 前，AI 编码助手根据 git diff 自动生成一个 Issue，描述本次变更。

**Issue 标题格式**：`[模块] 变更简述`

**Issue 正文模板**（AI 必须遵循）：

```markdown
## 变更概述
<!-- 1-3 句话说明做了什么、为什么做 -->

## 涉及文件
<!-- 列出主要变更文件及改动类型（新增/修改/删除） -->
- `backend/app/services/xxx.py` — 新增
- `frontend/src/views/xxx.vue` — 修改

## 技术要点
<!-- API 变更、数据库迁移、新增依赖等 -->

## 验收方式
<!-- 如何验证这个变更生效 -->
- [ ] pytest 通过
- [ ] 手动验证步骤：...
```

**Issue 标签**：AI 应自动添加对应模块标签（见第五章模块列表）+ 技术栈标签（`frontend` / `backend` / `wechat-miniprogram`）。

### PR 与 Issue 关联

- PR 描述中**必须**包含 `Closes #X`（X 为 Issue 编号），这样合并后自动关闭 Issue
- AI 助手在发 PR 时应同时完成：**建 Issue → 在 PR 描述中写 Closes #X → 提交 PR**
- 一个人从开发到 PR 到建 Issue 全流程自己闭环，不依赖他人"认领"

### Assignee 使用说明

- **Assignee 不是"谁认领"**，而是"谁实际在做/做完了"
- 有 write 权限的人随时可以改 assignee，不存在锁死问题
- AI 建 Issue 时，assignee 设为自己（当前开发者）
- 如果中途交接，新接手者改 assignee 即可


---

## 七、PR & Code Review

- PR 标题用中文，格式：`[模块] 简述`
- 禁止 force push 到 `main`
- 合并前确保 CI 通过（lint + test）
- 至少一人 Review 后可合并
- 合并后删除远程功能分支

---

## 八、环境变量

- 敏感配置（API Key、密钥）**仅存 `.env`，不提交**
- 新增环境变量需同步更新 `.env.example`
- 前端 Vite 环境变量以 `VITE_` 为前缀

---

## 九、合并冲突处理

- 优先保持双方功能完整，不做二选一删除
- 冲突解决后运行 `git diff --check` 确保无残留标记
- 合并后本地跑一遍关键流程（前端 `npm run dev`，后端 `pytest`）

---

## 十、数据库迁移

- 每次模型变更必须生成 Alembic 迁移文件
- 迁移文件名用英文描述：`add_geocoding_fields`
- 禁止手动修改已合并的迁移文件
- 运行前确保本地数据库已最新：`alembic upgrade head`

## ??Issue ??????Vibe Coding ???

### ???

```
vibe ?? ? ? PR ???? Issue ? PR ?? Issue ? ???????
```

### ? PR ??????

1. **?? Issue**??? git diff ?? Issue
2. **?? PR**??? `.github/PULL_REQUEST_TEMPLATE.md` ?????????? `Closes #X`
3. **PR ???**??? AI ???????????????? checklist

### Issue ????
- ????????? + `frontend` / `backend` / `wechat-miniprogram`
- ????????`high` / `medium` / `low`

---

## ???????

- ??????????????????
- ?? `requirements.txt` ? `package.json` ?? PR ?????
- ?????????????????????

---

## ???AI ????

- ???????????????"????????? PR ??"????????
- ? PR ?????? Issue + ??? + ?? Issue ???
- ????????????????????
- ??????????
- ?????????????????????

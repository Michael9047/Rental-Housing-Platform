# 🏗️ 项目结构性审计报告

> 审计日期：2026-08-08 | 范围：`backend/` + `frontend/` 全量代码

---

## 审计总览

| 类别 | Critical | High | Medium | Low | 合计 |
|------|----------|------|--------|-----|------|
| 错误处理 & 日志 | 0 | 3 | 2 | 1 | 6 |
| API/路由架构 | 2 | 4 | 5 | 2 | 13 |
| 安全/认证 | 0 | 7 | 0 | 3 | 10 |
| 数据库/模型 | 2 | 2 | 3 | 3 | 10 |
| 前端架构 | 2 | 2 | 6 | 3 | 13 |
| 登录链路 | 0 | 3 | 0 | 0 | 3 |
| 测试 | 0 | 0 | 1 | 1 | 2 |
| **合计** | **6** | **21** | **17** | **13** | **57** |

---

## 🔴 Critical — 影响功能正确性

### C1. `reviews.py` 路由从未注册 — 评价系统完全不可达

- **文件**：`backend/app/api/v1/router.py`
- **根因**：`routes/reviews.py` 定义了完整 CRUD + 聚合 API（`create_review`、`list_reviews`、`get_review_aggregation`），但 `router.py` 从未 import 或 `include_router`。
- **影响**：整个评价系统是死代码，前端调用永远 404。

### C2. `buildings.py` 函数名冲突 — `/buildings/public` 静默失效

- **文件**：`backend/app/api/v1/routes/buildings.py:184` ↔ `:779`
- **根因**：`list_public_buildings` 定义了两次（`/public` 和 `/public/list`），Python 第二个定义覆盖第一个。
- **影响**：`GET /buildings/public` 端点静默失效。

### C3. `confirm_import` 使用未定义变量 → NameError

- **文件**：`backend/app/api/v1/routes/imports.py:189`
- **根因**：`user_id=user_id` 但当前作用域只有 `current_user`（`user_id` 在另一个函数 `import_data` 中定义）。
- **影响**：导入确认端点运行时必定崩溃。

### C4. `contract_service.py:46` — Institute ID 错当 UnitType ID 查询

- **文件**：`backend/app/services/contract_service.py:46`
- **根因**：
  ```python
  property_obj = await self.session.get(Property, booking.institute_id)
  ```
  `Property` 是 `UnitType` 的别名，但 `booking.institute_id` 是 `institutes` 表的外键。
- **影响**：每次调用返回错误数据或 None，合同生成逻辑被破坏。

### C5. `EmbeddingJob.property_id` FK 指向已删除表

- **文件**：`backend/app/models/embedding_job.py:22`
- **根因**：`ForeignKey("properties.id")` — `properties` 表已在三层改两层重构中删除。
- **影响**：任何 EmbeddingJob INSERT 都失败。

### C6. `Property` 类型 `district` 三重复制

- **文件**：`frontend/src/types/property.ts:63,66,67`
- **根因**：同名字段 `district?: string | null` 声明了 3 次。
- **影响**：类型检查器不报错但行为未定义，数据序列化可能出问题。

### C7. `ComparePriority` 类型定义不一致

- **文件**：`frontend/src/types/agent.ts:211` vs `frontend/src/types/compare.ts:3`
- **根因**：`agent.ts` = `'balanced' | 'budget' | 'commute' | 'space'`（缺 `'safety'`），`compare.ts` = 多了 `'safety'`。
- **影响**：各自被不同 service 导入，运行时类型不匹配，对比功能可能走到错误的代码分支。

---

## 🟠 High — 安全/稳定性/数据风险

### 安全：未授权访问

#### H-SEC-1. 9 个端点无认证保护

| 端点 | 方法 | 暴露内容 |
|------|------|----------|
| `/buildings/{institute_id}/staff` | GET | 所有员工姓名/角色/电话 |
| `/geo/geocode` | POST | 消耗付费高德/Google 配额 |
| `/crystalroof/score` | GET/POST | 消耗外部爬虫配额 |
| `/commute/calculate` | POST | 消耗付费地图 API 配额 |
| `/commute/route` | POST | 消耗付费地图 API 配额 |
| `/pois/{property_id}/generate` | POST | 消耗 Google POI 配额 |
| `/pois/{property_id}` | GET | 暴露 POI 数据 |
| `/tenants/{tenant_id}` | GET | 租客完整 PII（姓名/电话/邮箱/学校） |
| `/users` (POST) | POST | 任意创建用户（可设 admin 角色） |

全部缺少 `Depends(get_current_user)` 或等价守卫。

#### H-SEC-2. SMS 验证码明文写入日志

- **文件**：`backend/app/core/security.py:56`、`backend/app/api/v1/routes/auth.py:257`
- **根因**：`logger.info("code=%s", code)` 直接把 6 位验证码写入日志。
- **影响**：有日志访问权的人可绕过 SMS 验证。

#### H-SEC-3. 前端环境变量中的 API Key 打入浏览器 bundle

- **文件**：`frontend/.env`
- **根因**：`VITE_AMAP_KEY` 和 `VITE_GM_KEY` 是 live 生产 key，Vite 编译时嵌入 JS 文件。
- **影响**：任意网站访客可从浏览器 Sources/Network 面板提取 API key。

#### H-SEC-4. 无登录暴力破解防护

- **文件**：`backend/app/api/v1/routes/auth.py:113-136`
- **根因**：无账户锁定、无渐进延迟、无 CAPTCHA。
- **影响**：可无限尝试撞库。

#### H-SEC-5. `UserCreate.password_hash` 允许绕过 bcrypt

- **文件**：`backend/app/schemas/user.py:19,24`
- **根因**：schema 中 `password_hash` 字段允许调用方直接注入任意 hash 值。
- **影响**：可写入弱 hash 或已知明文，绕过 `hash_password()`。

#### H-SEC-6. SMS 发送端点无认证

- **文件**：`backend/app/api/v1/routes/auth.py:238-268`
- **根因**：`POST /auth/send-sms-code` 无 auth，任何人可向任意手机号发短信。
- **影响**：财务滥用（SMS 按条计费）。

### 日志系统

#### H-LOG-1. 无持久化日志文件

- **文件**：`backend/app/core/logging.py:77-97`
- **根因**：`setup_logging()` 仅配置 `StreamHandler(sys.stdout)`，没有任何 `FileHandler` 或 `RotatingFileHandler`。
- **当前状态**：
  - 所有应用日志 → stdout
  - Dockerfile 也将 uvicorn 日志指向 stdout（`--access-logfile -`）
  - 进程重启/容器重建 → 全部日志丢失
- **影响**：
  - 无法事后排查问题（只能靠 F12 + 前端 toast 反推）
  - 生产事故无迹可查
  - 安全审计无日志可审
- **行业对比**：
  - **最低标准**：`RotatingFileHandler` + 30 天保留
  - **标配**：结构化 JSON 日志文件 → Filebeat → ELK / Loki
  - **完善**：以上 + Sentry APM + 告警规则
- **已有基础**：`JsonFormatter` 已实现（结构化 JSON 格式），只差一个 FileHandler。

> ✅ 10 行代码即可修复见文末修复建议。

### 架构

#### H-ARCH-1. 8 处 `except Exception: pass` 静默吞异常

- **文件**：`buildings.py` (6)、`unit_types.py:304`、`unit_type_service.py:44`
- **根因**：审计日志写入失败被静默丢弃，无任何日志输出。
- **影响**：操作成功但审计线索断裂，无法发现。

#### H-ARCH-2. 前后端错误响应格式不统一

- **后端全局 handler** 返回：`{"error": {"type": "...", "message": "...", "details": ...}}`
- **路由 `raise HTTPException`** 返回：`{"detail": "..."}`
- **影响**：前端 `extractErrorMessage()` 要处理两种格式，部分自定义格式漏网。

#### H-ARCH-3. 前端双重错误提示

- **文件**：`frontend/src/services/api.ts:62-83`
- **根因**：response interceptor 对所有非 401 错误自动调用 `ElMessage.error()`，各组件 `.catch()` 可能再次报错。
- **影响**：用户看到两条重复错误 toast。

#### H-ARCH-4. 事务边界不一致 — 无法组合多 Service 操作

- **根因**：Service 层方法内部自行 `commit()`，路由层也手动 `commit()`。路由调用两个 Service 时第一个已提交，第二个失败无法回滚。
- **影响**：跨 Service 操作可能产生不一致状态。

#### H-ARCH-5. `db/base.py` 只导入 16/36 个模型 → Alembic 可能误删表

- **文件**：`backend/app/db/base.py:2-17`
- **根因**：Alembic 通过 `from app.db.base import Base` 获取 metadata。未导入的 20 个模型的表在 autogenerate 时被视为需删除。
- **未导入模型**：`ContractTemplate`、`BuildingStaff`、`RepairRequest`、`AgentCart`、`CompareSession`、`PolicyConsent`、`PMSConnection`、`University`、`InstituteCommute` 等。

#### H-ARCH-6. `db/indexes.py` 引用已删除列名

- **文件**：`backend/app/db/indexes.py:61-71, 107-108`
- **根因**：`landlord_id` → 已改为 `bm_id`；`property_id` → 已改为 `unit_type_id`。
- **影响**：执行索引创建脚本会失败。

#### H-ARCH-7. `main.py` 硬编码公开端点绕过整体架构

- **文件**：`backend/app/main.py:79-103`
- **根因**：`@app.get("/api/v1/public/buildings")` 含内联 SQL、lambda 序列化，完全绕过 Service → Route → DI 体系。
- **影响**：逻辑与 `buildings.py` 中的实现不一致，且无法通过测试 dependency override 覆盖。

#### H-ARCH-8. 大量业务逻辑泄漏在路由文件中

- **最严重文件**：
  - `buildings.py` (845行) — SQL、图片拷贝、员工同步、审计日志全在路由里
  - `tenants.py` — 复杂 SQL join/去重、库存调整
  - `search_suggestions.py` (287行) — 搜索核心逻辑
- **影响**：不可测试、不可复用、路由文件超长难以维护。

### 前端架构

#### H-FE-1. localStorage 存储完整 User 对象

- **文件**：`frontend/src/stores/auth.ts:22,38`
- **根因**：`JSON.stringify(newUser)` 将含 `phone`、`email`、`role` 的完整对象存入 localStorage。
- **影响**：XSS 可读取全部用户敏感字段。

#### H-FE-2. `AdminLayout.vue` 从未被路由使用

- **文件**：`frontend/src/layouts/AdminLayout.vue`
- **根因**：定义了管理员专用侧边栏，但所有 admin 路由都使用 `DefaultLayout`。
- **影响**：死代码，管理员导航依赖 `AdminWorkspace.vue` 内嵌侧边栏，不一致。

### 登录链路

#### H-LOGIN-1. 审计日志阻塞登录 — 非关键操作可导致 500

- **文件**：`backend/app/api/v1/routes/auth.py:128-134`
- **根因**：`AuditService.create_log()` 无 try/except。审计表被锁/磁盘满/约束冲突 → 已验证密码的用户看到 500。
- **影响**：任何 DB 轻微故障都会让登录整体不可用。

#### H-LOGIN-2. `/auth/me` 失败导致半登录状态

- **文件**：`frontend/src/stores/auth.ts:58-62`
- **根因**：`login()` 先存 token（user=`{}`），然后调用 `/auth/me`。如果 `/auth/me` 失败，token 在 localStorage 但 user 为空对象，前端 router guard 会因 `!parsed.role` 清空 localStorage 跳回登录页。
- **影响**：用户凭据正确但困在登录循环。

#### H-LOGIN-3. 登录链路无重试/降级/熔断

- **根因**：`authenticate()` + `create_log()` + `/auth/me` 串行调用，任一失败整条链路断。
- **影响**：登录作为最基础入口，没有比业务功能更健壮。

---

## 🟡 Medium — 影响可维护性和开发效率

### M1. 无集中异常模块

自定义异常散落各 service（`ContractSignError`、`PMSError`、`DropboxSignError` 等），未注册到 `add_exception_handler`，未捕获的统一返回 500。

### M2. Service 层广泛使用内置异常类型

`ValueError`、`RuntimeError`、`LookupError` 用于业务错误。`_raise()` 按类型映射 HTTP 码（`ValueError→400`，`RuntimeError→409`）容易误判。

### M3. HTTP 状态码不统一

一半用 `status.HTTP_404_NOT_FOUND`，一半用裸整数 `404`（`payments.py` 全部裸整数）。

### M4. Schema 定义在路由文件中

`chat.py`、`room_confirmations.py`、`commute.py`、`me.py` 在路由文件中定义 Pydantic model（~15 个），而非 `schemas/`。

### M5. 路由前缀策略三套并存

构造函数内设（`buildings.py`）、`router.py` include 时设（大多数）、完全不设（`building_staff`、`wechat`）。

### M6. 23 个文件仍引用已删除的 `Property` 模型

通过 `_compat.py` 桥接 alias 运行，但旧的 `PropertyType` enum 与新的不同。

### M7. 前端 7/9 个 Store 无 error state

只有 `compare.ts` 暴露 `error` ref。组件无法判断操作是否失败。

### M8. 两套并行预订表单状态

旧 `bookingFlow.ts` (277行) + 新 `bookingPersonalInfo.ts` + `bookingEmergencyContact.ts` 共存。

### M9. 前端 21 处 `console.log/error` 违反 CLAUDE.md

分布在 13 个文件中，项目规范明确禁止。

### M10. 80% 业务类型定义在 service 文件而非 `types/`

`PaymentResponse`、`Contract`、`Building`、`TenantProfile` 等全部在 service 文件中。

### M11. `Notification` 接口在 `booking.ts` 和 `notification.ts` 中重复定义且形状不同

### M12. `Tenant.updated_at` 缺少 `onupdate`

行修改后时间戳不更新。

### M13. 遗留 Room 模型未清理

`RoomInventory`、`BookingRoomAssignment`、`RoomType` 别名等仍存在。

### M14. Alembic 含 14+ 个 merge 迁移，分支极度复杂

### M15. 测试缺口

无 Institute CRUD、UnitType 搜索、并发抢房、Webhook 幂等测试。

### M16. `login()` 用 `{} as User` 做临时占位

TypeScript 类型断言掩盖了 user 对象暂时为空的实际情况。

### M17. `db/base.py` 遗漏模型 vs `models/__init__.py` 全量导入 — 元数据来源不一致

---

## 🟢 Low — 改进建议

| ID | 问题 | 位置 |
|----|------|------|
| L1 | 无 CSRF token 保护 | 全局 |
| L2 | `router.py` 存在注释掉的死代码（`ai_search`、`ml`、`pms`） | `router.py` |
| L3 | 前端 `RoomManagement.vue.bak` 在源码树 | `views/` |
| L4 | `requiresBdManager` meta 从未被任何路由使用 | `router/index.ts` |
| L5 | agent SSE 用原生 `fetch()` 绕过 axios 拦截器 | `services/agent.ts` |
| L6 | `profile.ts` 标注 "Stub — PR #30" | `services/profile.ts` |
| L7 | OWASP 自查清单是硬编码 dict 非真实扫描 | `core/security_audit.py` |
| L8 | `University`、`InstituteCommute`、`PaymentWebhookEvent` 无任何时间戳 | `models/` |
| L9 | `pgvector` 16 个测试全部需 `--run-pgvector` 默认跳过 | `tests/` |
| L10 | `backend.log` 813KB 未 gitignored（可能含敏感数据） | 项目根目录 |
| L11 | `main.py` 速率限制初始化失败无日志 | `main.py:63-64` |
| L12 | `AgentSearchCandidate` 的 `property_id` 和 `unit_type_id` 指向同一张表 — 冗余列 | `agent_intelligence.py` |
| L13 | `Contract` 模型无到 `Institute` 的关系 — 无法直接从合同导航到关联楼栋 | `contract.py` |

---

## 📋 修复建议

### 日志落盘 — 最少改动（10 行）

```python
# backend/app/core/logging.py — setup_logging() 中添加
from logging.handlers import RotatingFileHandler
from pathlib import Path

Path("logs").mkdir(exist_ok=True)
file_handler = RotatingFileHandler(
    "logs/app.log", maxBytes=10 * 1024 * 1024, backupCount=30, encoding="utf-8"
)
file_handler.setFormatter(JsonFormatter() if settings.environment == "production" else ColoredFormatter())
file_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
root.addHandler(file_handler)
```

效果：所有日志同时写 stdout + `logs/app.log`，JSON 格式，单个文件最大 10MB，保留 30 个滚动文件，可直接 `grep`/`jq` 审计。

### 登录加固 — 最少改动（5 行）

```python
# backend/app/api/v1/routes/auth.py — login() 中 128 行
# 将 AuditService.create_log 包在 try/except 中
try:
    await AuditService(session).create_log(
        user_id=user.id, action="user_login", ...
    )
except Exception:
    logger.exception("Audit log failed for user %d login", user.id)

return TokenResponse(access_token=auth_service.create_access_token(user))
```

### 修复优先级建议

```
C3 → C4 → C5 → C1 → C2  (Bug — 功能不工作)
  ↓
H-SEC-1 → H-LOGIN-1 → H-LOGIN-2 → H-LOG-1  (安全 + 稳定性)
  ↓
H-SEC-2 → H-SEC-3 → H-SEC-4 → H-SEC-5 → H-SEC-6  (安全增强)
  ↓
H-ARCH-1 → H-ARCH-4 → H-ARCH-5 → H-ARCH-6  (架构基础)
  ↓
M 类 + L 类（按模块渐进修复）
```

# 🔴 错误处理 & 日志系统专项审计

> 审计日期：2026-08-09 | 对比基准：成熟行业实践（Sentry + 结构化日志 + 用户友好错误 UX）

---

## 一、你遇到的"屏幕上跳大量长代码报错" — 根因分析

### 根因链条

```
用户操作 → 后端异常 → debug=True 返回完整 str(exc) → 前端 ElMessage.error() 显示 → 用户看到满屏报错
```

具体来说有 **4 层问题叠加**：

### 第 1 层：后端 debug 模式泄露内部错误信息

**文件**：`backend/app/core/config.py:13`
```python
debug: bool = True  # ← 默认值就是 True！
```

**文件**：`backend/app/core/logging.py:226`
```python
msg = str(exc) if settings.debug else "Internal server error"
```

当 `debug=True`（当前默认值），**任何未捕获异常**的 `str(exc)` 直接返回给前端。对于数据库错误、SQLAlchemy 错误、网络错误，`str(exc)` 可能包含：

- 完整 SQL 语句（含参数值）
- 表名、列名、约束名
- 连接字符串片段
- 长调用栈信息
- 第三方库内部错误详情

**成熟行业做法**：
- 生产环境永远返回 `"Internal server error"`（通用消息）
- 需要调试时返回一个 `error_id`（UUID），用户可提供给客服查询
- 详细错误记录在日志文件/Sentry 中

### 第 2 层：FastAPI debug 模式还会渲染 HTML 错误页

当 `debug=True` 且请求来自浏览器直接访问（非 API 调用），FastAPI 会渲染完整的 HTML traceback 页面，包含：
- 每层调用栈的代码片段
- 局部变量值
- 文件系统路径

### 第 3 层：前端 axios 拦截器对所有错误弹 toast

**文件**：`frontend/src/services/api.ts:92-94`
```typescript
if (error.config?._handled) return Promise.reject(error)
const message = extractErrorMessage(error)
if (message) ElMessage.error(message)  // ← 任何非 401 错误都弹 toast
```

`extractErrorMessage()` 尽力提取消息，但如果后端返回的是长错误字符串，就直接显示长错误字符串。没有长度截断，没有"详情"折叠。

### 第 4 层：组件层 `console.error` 泄露完整响应

**文件**：`frontend/src/views/booking/BookingReview.vue:65-66`
```typescript
console.error('[authorization] proceed payment failed', {
  status: error?.response?.status,
  response: error?.response?.data,  // ← 完整响应体
  url: error?.config?.url,
  error
})
```

**违反 CLAUDE.md 规范**：项目规范明确禁止 `console.log/error`，但前端有 21+ 处违规。

---

## 二、日志系统 — 现状与差距

### 现状：日志只写 stdout，重启即丢失

**文件**：`backend/app/core/logging.py:77-97`

```python
def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    # ...只创建 StreamHandler(sys.stdout)
    root.addHandler(handler)
    # ❌ 没有任何 FileHandler / RotatingFileHandler
```

**影响**：
- 进程重启 / 容器重建 → 全部日志消失
- 无法排查"昨天下午用户报的错是什么"
- 安全事件无日志可审计
- 本地调试时，终端窗口关闭后日志全部丢失
- `backend.log`（813KB）在项目根目录未 gitignored，可能是旧的临时日志

### 已有基础（无需从零开始）

| 已有组件 | 状态 |
|----------|------|
| `JsonFormatter`（结构化 JSON） | ✅ 已实现 |
| `ColoredFormatter`（开发用彩色输出） | ✅ 已实现 |
| `RequestLoggingMiddleware`（请求/响应日志） | ✅ 已实现 |
| `mask_sensitive()`（敏感字段脱敏） | ✅ 已实现 |
| `register_exception_handlers()`（全局异常处理） | ✅ 已实现 |
| **FileHandler（落盘）** | ❌ **缺失** |
| **日志轮转** | ❌ **缺失** |
| **日志级别动态调整** | ❌ **缺失** |
| **Sentry/错误追踪集成** | ❌ **缺失** |

### 行业对比

| 级别 | 方案 | 本项目 |
|------|------|--------|
| 最低标准 | `RotatingFileHandler` + 30 天保留 | ❌ |
| 标配 | 结构化 JSON 日志文件 → Filebeat → ELK/Loki | ❌ |
| 标配 | Sentry / GlitchTip 错误追踪 | ❌ |
| 完善 | 以上 + Prometheus 告警规则 | ⚠️ 有 Prometheus 但无告警 |

---

## 三、补充发现（不在 08-08 审计报告中）

### 🔴 新增 Critical 发现

#### NEW-C1. 前端 PersonalInfo.vue 将完整 PII 打入 console.error

**文件**：`frontend/src/views/booking/PersonalInfo.vue:184-191`
```typescript
console.error('[personal-info] submit failed', {
  error, status, data, url, method,
  payload  // ← 包含姓名、电话、邮箱、地址等完整个人信息！
})
```
**影响**：任何打开 F12 的人都能看到上一个用户提交的个人身份信息。严重隐私泄露。

#### NEW-C2. 前端 `.env` 和 `overpass.ts` 硬编码 API Key

**文件**：`frontend/.env:1-2` + `frontend/src/services/overpass.ts:34`
```
VITE_AMAP_KEY=d236c5d4b0bb068d9da00e0066a8f85c
VITE_GM_KEY=AIzaSyA2TFWRlLOG72sJLckOBa2zWq9L-rDotzc
// overpass.ts:34 还有同样的 AMAP key 作为 fallback
```
**影响**：Vite 编译时这些 key 嵌入 JS bundle，任何人可从浏览器 Sources 面板提取。

#### NEW-C3. 4 个路由将 `str(exc)` 直接返回给客户端

| 文件 | 行号 | 代码 |
|------|------|------|
| `ai_search.py` | 90 | `detail=f"AI 解析服务暂时不可用: {e}"` |
| `ml.py` | 94 | `detail=f"Parse failed: {exc}"` |
| `pms.py` | 131 | `detail=f"Sync failed: {exc}"` |
| `agent.py` | 509 | SSE stream 发送 `{'error': str(exc)}` |

这些与 `logging.py:226` 一样，把原始异常字符串暴露给前端。

#### NEW-C4. `App.vue` 全局错误覆盖层泄露文件路径

**文件**：`frontend/src/App.vue:19-24`
```typescript
window.addEventListener('error', (e) => {
  error.value = `[${e.filename?.split('/').pop()}:${e.lineno}] ${e.message}`
  // ↑ 文件名 + 行号暴露给用户
})
window.addEventListener('unhandledrejection', (e) => {
  error.value = `[Promise] ${e.reason?.message || e.reason}`
  // ↑ 原始 rejection reason 暴露给用户
})
```

### 🟠 新增 High 发现

#### NEW-H1. 网络错误无用户提示

**文件**：`frontend/src/services/api.ts:67-96`

response interceptor 只处理 `error.response` 存在的情况。当服务器不可达（`error.response === undefined`）时，`extractErrorMessage()` 返回 `null`，用户完全看不到错误提示——页面就卡住了。

#### NEW-H2. 25+ 处 `except Exception: pass` 静默吞错

后端审计发现的应用代码（非脚本）中有超过 25 处静默吞异常：

| 文件 | 数量 | 影响 |
|------|------|------|
| `buildings.py` | 5 处 | 审计日志写入失败不可见 |
| `auth.py` | 2 处 | 欢迎邮件失败不可见 |
| `booking_service.py` | 1 处 | 确认消息发送失败不可见 |
| `payment_tasks.py` | 2 处 | 支付通知邮件失败不可见 |
| `unit_types.py` + `unit_type_service.py` | 2 处 | 操作日志/名称查询失败不可见 |
| `property_service.py` | 3 处 | Redis 连接关闭失败不可见 |
| `embedding_cache.py` + `search_state.py` | 2 处 | Redis 关闭失败不可见 |
| `outlier_detector.py` + `risk_evaluator.py` | 2 处 | 日期解析/距离计算失败不可见 |
| `contracts.py` + `tenants.py` | 2 处 | 文件删除/名称查询失败不可见 |

所有地方都应该至少加一行 `logger.warning()`。

#### NEW-H3. `main.ts` 全局 error handler 二次抛出导致双处理

**文件**：`frontend/src/main.ts:28-32`
```typescript
app.config.errorHandler = (err: unknown) => {
  if (err instanceof Error && err.message.includes('ResizeObserver')) return
  console.error(err)
  throw err  // ← 重新抛出，导致 App.vue 的 onErrorCaptured 又处理一次
}
```

#### NEW-H4. 无请求重试机制

整个前端没有任何重试逻辑。网络瞬断、5xx 错误都不会自动重试。`axios-retry` 一行安装即可解决。

### 🟡 新增 Medium 发现

- **NEW-M1**：`embedding_tasks.py:72` 将 `str(exc)[:2000]` 存入数据库 `error_message` 列，可能包含内部路径信息
- **NEW-M2**：`_handled` 标记模式无 TypeScript 类型声明，容易遗漏
- **NEW-M3**：无组件级错误边界——任一组件报错，整个 App 崩溃
- **NEW-M4**：多个页面（Home、PropertyDetail）加载失败时只是空白页，无错误提示
- **NEW-M5**：`PropertyCreate`、`PropertyUpdate`、`RoomType` 类型被 import 但从未定义在 `types/property.ts` 中——`vue-tsc` 严格模式会编译失败
- **NEW-M6**：全局注册 200+ Element Plus 图标（`main.ts:17-19`），实际只用 16 个——打包体积浪费
- **NEW-M7**：路由器 `beforeEach` guard 直接读 `localStorage` 而非 Pinia store——认证状态双源头
- **NEW-M8**：`Property` 类型缺少 `rent_period` 字段——7 个文件中被迫用 `as any` 访问
- **NEW-M9**：`vite.config.ts` 无 `build` 配置段——无 manualChunks、无 sourcemap 控制、无 target 声明
- **NEW-M10**：无 `.env.example` / `.env.production` 文件
- **NEW-M11**：前端仅 8 个测试文件（覆盖 booking 流程为主），其余 60+ views、30+ services 零测试

### 🟢 新增 Low 发现

- **NEW-L1**：`Property.district` 字段在 `types/property.ts:63-67` 重复声明 3 次
- **NEW-L2**：暗色模式 composable 存在但无 CSS 变量覆盖——暗色模式不可用
- **NEW-L3**：`xlsx` 包（~500KB）未动态导入——所有页面都加载
- **NEW-L4**：可点击卡片（PropertyCard、MiniPropertyCard）无键盘无障碍支持（无 role/tabindex）
- **NEW-L5**：`RoomManagement.vue.bak` 备份文件在源码树中

### 原有 NEW 发现（保留）

### NEW-1. 🔴 `generic_exception_handler` 的 error_type 泄露类名

**文件**：`backend/app/core/logging.py:244`
```python
return _build_error_response(500, msg, error_type)  # error_type = type(exc).__name__
```

返回 `{"error": {"type": "IntegrityError", "message": "duplicate key value violates unique constraint..."}}` — 用户不需要知道这是 `IntegrityError` 还是 `ProgrammingError`。

### NEW-2. 🔴 前端无全局 toast 去重/排队机制

当多个 API 调用同时失败（如页面加载时多个请求并行），用户看到 N 条 error toast 同时弹出。`ElMessage.error()` 没有去重、没有合并、没有优先级。

### NEW-3. 🔴 `App.vue` 错误覆盖层用户体验差

**文件**：`frontend/src/App.vue:13-17`
```html
<div v-if="error" style="...font-family:monospace">
  <pre>{{ error }}</pre>  <!--原始错误消息直接展示给用户-->
</div>
```

这是一个全屏白色错误页，显示原始 JS 错误信息。对用户来说这是"网站崩溃了"。应该显示友好的错误页面（"出错了，请刷新重试"），并提供"导出错误报告"按钮。

### NEW-4. 🟠 前端组件大量静默吞错

| 文件 | 代码 | 问题 |
|------|------|------|
| `BuildingList.vue:379` | `catch(e){}` | 加载失败无声无息 |
| `BuildingList.vue:380` | `catch(e){}` | 回收站加载失败无声 |
| `BuildingStaff.vue:92` | `catch { /* */ }` | 删除员工失败不提示 |
| `CreateProperty.vue:295` | `catch { /* */ }` | 楼栋列表加载失败不提示 |

用户操作后什么都没发生，不知道是成功了还是失败了。

### NEW-5. 🟠 错误响应格式三套并存

| 来源 | 格式 |
|------|------|
| 全局 exception handler | `{"error": {"type": "...", "message": "...", "details": ...}}` |
| 路由 `raise HTTPException` | `{"detail": "..."}` |
| FastAPI 默认验证错误 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |

前端 `extractErrorMessage()` 要兼容三种格式，仍有漏网之鱼。

### NEW-6. 🟡 `main.py` 速率限制初始化失败静默吞错

**文件**：`backend/app/main.py:63-64`
```python
except Exception:
    pass  # ← Redis 连不上 → 整个速率限制悄悄不生效，无任何日志
```

### NEW-7. 🟡 `.env` 默认值包含可用的数据库凭据

**文件**：`backend/app/core/config.py:16-17,27,29`
```python
database_url: str = Field(default="postgresql+asyncpg://rental:rental@localhost:5432/rental_housing")
auth_secret_key: str = Field(default="dev-only-change-me")
```

如果运维忘记设环境变量，会用这些默认值启动——`dev-only-change-me` 不是安全的 fallback。

### NEW-8. 🟡 无请求 ID 传递给前端

后端 `RequestLoggingMiddleware` 生成了 `request_id`，但从未在响应头中返回给前端。当用户报错时，无法关联前端截图和后端日志。

---

## 四、修复建议（按优先级）

### P0 — 立即修复（阻止用户看到长报错）

#### 1. 区分 debug 模式下的错误响应（1 行修改）

```python
# backend/app/core/logging.py:226 — generic_exception_handler
msg = str(exc) if settings.debug else "Internal server error"
# 改为 ↓
msg = "Internal server error"  # 始终隐藏内部细节
# 在日志中记录完整异常（已有的 logger.error 已经做了）
```

同时在响应中加 `error_id`（UUID），方便用户反馈时定位：

```python
import uuid
error_id = str(uuid.uuid4())
logging.getLogger("app.error").error("error_id=%s %s", error_id, msg)
return _build_error_response(500, f"Internal server error (ref: {error_id})", "internal_error")
```

#### 2. 生产环境关闭 debug（1 行修改）

```bash
# .env 或环境变量
DEBUG=false
```

#### 3. 前端错误消息截断

```typescript
// frontend/src/services/api.ts:93
if (message) {
  const truncated = message.length > 200 ? message.slice(0, 200) + '…' : message
  ElMessage.error(truncated)
}
```

### P1 — 本周修复（日志落盘 + 错误追踪）

#### 4. 日志文件落盘（10 行新增，08-08 审计已有方案）

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

#### 5. 响应头返回 request_id

```python
# backend/app/core/logging.py — RequestLoggingMiddleware.dispatch() 返回前
response.headers["X-Request-ID"] = request_id
```

#### 6. 清理前端 console.error/console.log（21 处）

全局替换为统一的 `logError()` 工具函数，只在 development 模式下输出。

### P2 — 本月修复（架构改进）

#### 7. 统一错误响应格式

- 所有路由统一使用全局 exception handler 格式
- 废弃 `raise HTTPException(detail="...")`，改用自定义 BusinessException
- 建立错误码体系（`ERR_BOOKING_001` 等），前端可根据错误码做 i18n

#### 8. 前端全局 toast 管理

- 实现 toast 去重（相同错误 2 秒内不重复弹出）
- 实现 toast 合并（"3 个请求失败" 而不是弹 3 条）
- 致命错误用 `ElNotification`（需用户点击关闭），普通错误用 `ElMessage`

#### 9. 优雅的错误覆盖层

`App.vue` 的错误覆盖层改为友好的"出错了"页面，提供刷新按钮和错误报告导出。

#### 10. 引入 Sentry / GlitchTip

```python
# 生产环境
import sentry_sdk
sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)
```

---

## 五、后端安全专项审计（补充）

### 🔴 SEC-C1. `.env` 含真实 API Key 和密钥

**文件**：`backend/.env`

| 行 | 密钥 | 风险 |
|----|------|------|
| 9 | `AUTH_SECRET_KEY=change-me-in-production` | JWT 签名密钥可被猜测 |
| 17 | `AMAP_WEB_KEY=d236c5d4b0bb068d9da00e0066a8f85c` | 高德 API key |
| 20 | `ORS_API_KEY=eyJvcmc...` (JWT) | OpenRouteService key |
| 31-32 | `SMS_ACCESS_KEY_ID` + `SMS_ACCESS_KEY_SECRET` | 阿里云短信凭据 |
| 42-43 | `SMTP_USER=3158309731@qq.com` + `SMTP_PASSWORD=...` | QQ 邮箱凭据 |
| 50-51 | `DM_ACCESS_KEY_ID` + `DM_ACCESS_KEY_SECRET` | 阿里云 DirectMail |
| 66 | `DEEPSEEK_API_KEY=sk-d2d0eb...` | DeepSeek API key |
| 82 | `ZHIPU_API_KEY=a90c443a...` | 智谱 AI key |
| 83 | `GM_API_KEY=AIzaSyA2TFW...` | Google Maps key |

**8 个真实密钥存储在 `.env` 文件中。** 即使 gitignored，备份/截图/分享都可能泄露。

### 🔴 SEC-C2. SMS 和 DirectMail 共享同一阿里云 AK

`.env` 第 31-32 行和 50-51 行使用了 **同一对** Access Key。违反最小权限原则——SMS 服务和邮件服务应使用不同子账号。

### 🟠 SEC-H1. 微信登录用户密码设为 openid

**文件**：`backend/app/services/auth_service.py:68,93`
```python
password_hash=hash_password(session_data.openid),
```
openid 是公开可推导的值——任何人知道用户 openid 即可尝试密码登录。

### 🟠 SEC-H2. Refresh Token 无服务端吊销机制

Refresh token 是纯 JWT（无状态），签发后无法撤销。泄露后攻击者可无限刷新直至 7 天过期。

### 🟠 SEC-H3. SMS 验证码验证无暴力破解防护

**文件**：`backend/app/api/v1/routes/auth.py:272-278`

发送有 60s 冷却，但**验证端点无尝试限制**。攻击者可在 5 分钟窗口内暴力破解 6 位验证码。

### 🟠 SEC-H4. 短信验证码明文写入日志

**文件**：`backend/app/core/security.py:56` + `auth.py:257`
```python
logger.info("code=%s", code)  # ← 6 位验证码明文
```

### 🟡 SEC-M1. CORS 生产配置可能违反浏览器规范

`allow_headers=["*"]` + `allow_credentials=True` 组合在生产环境会被浏览器拒绝。

### 🟡 SEC-M2. Redis 连接每次操作新建

**文件**：`backend/app/core/security.py:45-48`

`store_sms_code`、`verify_sms_code` 等每次调用新建 Redis 连接——高频场景下浪费。

---

## 六、汇总统计

### 全部审计发现

| 来源 | Critical | High | Medium | Low |
|------|----------|------|--------|-----|
| 08-08 结构审计 | 6 | 21 | 17 | 13 |
| 错误处理 & 日志（08-09） | 4 | 2 | 4 | 1 |
| 前端错误 UX（08-09） | 2 | 3 | 4 | 2 |
| 后端安全（08-09） | 2 | 4 | 2 | 0 |
| 前端架构（08-09） | 0 | 0 | 7 | 5 |
| **合计** | **14** | **30** | **34** | **21** |

**总计：99 个问题**

### P0 立即修复清单（5 项）

| # | 修复 | 影响 | 改动量 |
|----|------|------|--------|
| 1 | `logging.py:226` — 永远返回通用错误消息 | 阻止用户看到长报错 | 1 行 |
| 2 | `.env` — 设 `DEBUG=false` | 同上 + 关闭 FastAPI traceback HTML | 1 行 |
| 3 | `logging.py` — 加 `RotatingFileHandler` | 日志落盘，重启不丢失 | 10 行 |
| 4 | `api.ts:93` — 错误消息截断 200 字符 | 防止超长 toast | 3 行 |
| 5 | `PersonalInfo.vue:184` — 移除 console.error 中的 payload | 阻止 PII 泄露到浏览器控制台 | 1 行 |

---

## 七、总结

| 维度 | 现状 | 行业标准 | 差距 |
|------|------|----------|------|
| 错误对用户可见性 | debug 模式发送原始异常文本 | 用户只看到通用错误消息 + error_id | 🔴 大 |
| 日志持久化 | stdout only | RotatingFileHandler + 远程收集 | 🔴 大 |
| 错误追踪 | 无 | Sentry/GlitchTip | 🔴 大 |
| 错误码体系 | 无（靠 HTTP 状态码 + 字符串） | 结构化错误码 + i18n | 🟠 中 |
| 前端错误 UX | 弹 toast + 可能的白屏覆盖层 | Toast 去重 + 友好错误页面 | 🟠 中 |
| request_id 关联 | 有（内部）但不传递给前端 | 响应头 X-Request-ID | 🟡 小 |
| 敏感信息脱敏（日志） | ✅ 已实现 | ✅ | ✅ 达标 |
| 结构化日志格式 | ✅ JsonFormatter 已实现 | ✅ | ✅ 达标 |

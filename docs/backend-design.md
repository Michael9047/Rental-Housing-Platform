# 租房平台 — 后端设计文档

> **项目名称**：Rental Housing Matching System  
> **技术栈**：FastAPI + PostgreSQL + pgvector + Celery + Redis  
> **最后更新**：2026-06-30  

---

## 一、技术栈总览

| 层次 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI 0.112 | 异步 REST API |
| 数据库 | PostgreSQL + asyncpg | 主数据库 |
| 向量检索 | pgvector 0.3 | 语义搜索（1536 维 embedding） |
| 缓存/队列 | Redis 5.0 | Celery 消息队列 + 缓存 |
| 异步任务 | Celery 5.4 | 长耗时后台任务 |
| 认证 | JWT (PyJWT + bcrypt) | Bearer Token |
| AI | OpenAI (text-embedding-3-small, gpt-4o) | Embedding + 聊天 |
| 地图 | 高德地图 API | 地理编码 + 周边 POI |
| 监控 | Prometheus | 指标暴露 |
| 微信 | 微信小程序 API | 登录 + 手机号 |

---

## 二、数据库设计

### 2.1 核心表概览（14 张表）

```
users ─────────────────────────────────────────────────────────────────
  │
  ├── properties ───── property_images
  │      │
  │      ├── embedding_jobs
  │      ├── property_pois
  │      └── bookings ──── contracts
  │             │              └── payments
  │             └── reviews
  │
  ├── institutes ── properties (关联)
  │      └── reviews
  │
  ├── chat_sessions ── chat_messages
  ├── notifications
  ├── advertisements ── ad_impressions
  ├── saved_searches
  ├── data_imports
  └── audit_logs
```

### 2.2 表结构详解

#### users（用户表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `username` | VARCHAR(100) | UNIQUE, NOT NULL | 用户名 |
| `password_hash` | VARCHAR(255) | NULL | bcrypt 哈希 |
| `phone` | VARCHAR(32) | UNIQUE | 手机号 |
| `wechat_openid` | VARCHAR(128) | UNIQUE | 微信 OpenID |
| `email` | VARCHAR(255) | UNIQUE | 邮箱 |
| `role` | ENUM(tenant,landlord,bd_manager,admin) | NOT NULL, DEFAULT tenant | 角色 |
| `status` | ENUM(active,disabled,deleted) | NOT NULL, DEFAULT active | 状态 |
| `created_at` | TIMESTAMPTZ | NOT NULL | 创建时间 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | 更新时间 |

- **租客 (tenant)**：浏览房源、预约看房、支付押金、签署合同
- **房东 (landlord)**：发布房源、确认预约
- **BD经理 (bd_manager)**：录入公寓管理机构
- **管理员 (admin)**：全局管理、审核

---

#### institutes（公寓管理机构表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `name` | VARCHAR(200) | NOT NULL | 机构名称 |
| `address` | VARCHAR(300) | NULL | 地址 |
| `contact_phone` | VARCHAR(32) | NULL | 联系电话 |
| `contact_email` | VARCHAR(255) | NULL | 联系邮箱 |
| `logo_url` | VARCHAR(500) | NULL | Logo URL |
| `description` | TEXT | NULL | 描述 |
| `has_api` | BOOLEAN | NOT NULL, DEFAULT false | 是否有 API 接入 |
| `api_config` | JSON | NULL | API 配置 |
| `status` | ENUM(pending,active,suspended) | NOT NULL, DEFAULT pending | 状态 |
| `created_by` | INT | FK→users.id, NOT NULL | 创建者(BD经理) |
| `reviewed_by` | INT | FK→users.id | 审核者(管理员) |

---

#### properties（房源表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `landlord_id` | INT | FK→users.id, NOT NULL | 房东 ID |
| `institute_id` | INT | FK→institutes.id, NULL | 关联机构 |
| `title` | VARCHAR(200) | NOT NULL | 标题 |
| `description` | TEXT | NULL | 描述 |
| `address` | VARCHAR(300) | NOT NULL | 地址 |
| `district` | VARCHAR(100) | NOT NULL, INDEX | 区域 |
| `price_monthly` | NUMERIC(12,2) | NOT NULL, CHECK ≥0 | 月租金 |
| `area_sqm` | NUMERIC(8,2) | NULL, CHECK >0 | 面积 |
| `bedrooms` | INT | NOT NULL, DEFAULT 0, CHECK ≥0 | 卧室数 |
| `bathrooms` | INT | NOT NULL, DEFAULT 0, CHECK ≥0 | 卫生间数 |
| `property_type` | ENUM(apartment,house,studio,shared) | NOT NULL, DEFAULT apartment | 类型 |
| `status` | ENUM(available,rented,maintenance,offline) | NOT NULL, DEFAULT available, INDEX | 状态 |
| `latitude` | NUMERIC(9,6) | NULL | 纬度 |
| `longitude` | NUMERIC(9,6) | NULL | 经度 |
| `deposit_amount` | INT | NULL, DEFAULT 1000 | 押金金额 |
| `service_fee_rate` | FLOAT | NULL, DEFAULT 0.10 | 服务费比例 |
| `embedding` | VECTOR(1536) | NULL | 语义向量 |

- 联合索引：`(district, status)`

---

#### property_images（房源图片表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `property_id` | INT | FK→properties.id, CASCADE, INDEX | 关联房源 |
| `filename` | VARCHAR(255) | UNIQUE, NOT NULL | 存储文件名(UUID) |
| `original_name` | VARCHAR(255) | NOT NULL | 原始文件名 |
| `mime_type` | VARCHAR(50) | NOT NULL | MIME 类型 |
| `file_size` | INT | NOT NULL | 文件大小(字节) |
| `sort_order` | INT | NOT NULL, DEFAULT 0 | 排序 |
| `is_primary` | BOOLEAN | NOT NULL, DEFAULT false | 是否封面图 |

---

#### bookings（预约看房表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `tenant_id` | INT | FK→users.id, CASCADE, INDEX | 租客 ID |
| `property_id` | INT | FK→properties.id, CASCADE, INDEX | 房源 ID |
| `landlord_id` | INT | FK→users.id, CASCADE, INDEX | 房东 ID |
| `status` | ENUM(pending,approved,rejected,cancelled,completed) | NOT NULL, DEFAULT pending | 状态 |
| `message` | TEXT | NULL | 留言 |
| `scheduled_date` | VARCHAR(32) | NULL | 预约日期 |
| `deposit_amount` | INT | NULL | 押金金额 |
| `service_fee` | INT | NULL | 服务费 |
| `deposit_status` | VARCHAR(20) | DEFAULT "unpaid" | 押金状态 |
| `payment_transaction_id` | VARCHAR(255) | NULL | 支付流水号 |

**状态流转**：
```
pending → approved / rejected / cancelled
approved → completed
```

---

#### payments（支付表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | UUID(36) | PK | UUID 主键 |
| `booking_id` | INT | FK→bookings.id, CASCADE, INDEX | 关联预约 |
| `user_id` | INT | FK→users.id, CASCADE, INDEX | 付款人 |
| `amount` | INT | NOT NULL | 金额(分) |
| `transaction_id` | VARCHAR(255) | NULL | 微信交易号 |
| `status` | VARCHAR(20) | DEFAULT "pending" | pending/success/failed/refunded |
| `payment_method` | VARCHAR(50) | DEFAULT "wechat_pay" | 支付方式 |
| `paid_at` | TIMESTAMPTZ | NULL | 支付时间 |

---

#### contracts（电子合同表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | UUID(36) | PK | UUID 主键 |
| `booking_id` | INT | FK→bookings.id, CASCADE, UNIQUE, INDEX | 关联预约(一对一) |
| `tenant_id` | INT | FK→users.id, CASCADE, INDEX | 租客 |
| `property_id` | INT | FK→properties.id, CASCADE, INDEX | 房源 |
| `template_name` | VARCHAR(100) | DEFAULT "standard_lease" | 模板名 |
| `content` | TEXT | NOT NULL | 合同文本 |
| `status` | VARCHAR(20) | DEFAULT "draft" | draft/signed |
| `signed_at` | TIMESTAMPTZ | NULL | 签署时间 |
| `file_path` | VARCHAR(500) | NULL | 文件路径 |

---

#### reviews（评价表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `tenant_id` | INT | FK→users.id, CASCADE, INDEX | 租客 |
| `institute_id` | INT | FK→institutes.id, CASCADE, INDEX | 被评价机构 |
| `booking_id` | INT | FK→bookings.id, UNIQUE, INDEX | 关联预约(一对一) |
| `rating` | INT | NOT NULL | 评分 1-5 |
| `comment` | TEXT | NULL | 评价内容 |
| `status` | ENUM(pending,approved,rejected) | NOT NULL, DEFAULT pending | 审核状态 |

---

#### notifications（通知表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `user_id` | INT | FK→users.id, CASCADE, INDEX | 接收者 |
| `type` | ENUM(booking_created,booking_approved,booking_rejected,…) | NOT NULL | 通知类型 |
| `title` | VARCHAR(200) | NOT NULL | 标题 |
| `content` | TEXT | NULL | 内容 |
| `is_read` | BOOLEAN | NOT NULL, DEFAULT false | 已读标记 |

---

#### chat_sessions / chat_messages（聊天表）

**chat_sessions**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `user_id` | INT | FK→users.id, CASCADE, INDEX | 用户 |
| `session_id` | VARCHAR(64) | UNIQUE, INDEX | 会话标识(UUID) |
| `title` | VARCHAR(200) | NULL | 会话标题 |
| `status` | ENUM(active,closed) | NOT NULL, DEFAULT active | 状态 |

**chat_messages**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `session_id` | INT | FK→chat_sessions.id, CASCADE, INDEX | 所属会话 |
| `role` | ENUM(user,assistant,system) | NOT NULL | 角色 |
| `content` | TEXT | NOT NULL | 消息内容 |
| `metadata` | JSON | NULL | 元数据 |

---

#### advertisements / ad_impressions（广告表 — v2）

**advertisements**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `title` | VARCHAR(200) | NOT NULL | 广告标题 |
| `image_url` | VARCHAR(500) | NOT NULL | 图片 URL |
| `target_url` | VARCHAR(500) | NULL | 跳转链接 |
| `district` | VARCHAR(100) | INDEX | 定向区域 |
| `placement` | VARCHAR(50) | NOT NULL, INDEX | 广告位 |
| `budget` | FLOAT | NULL | 预算 |
| `cost_per_click` | FLOAT | NULL | CPC |
| `start_date` | VARCHAR(32) | NOT NULL | 开始日期 |
| `end_date` | VARCHAR(32) | NOT NULL | 结束日期 |
| `status` | ENUM(draft,active,paused,ended,rejected) | NOT NULL, DEFAULT draft, INDEX | 状态 |
| `created_by` | INT | FK→users.id, CASCADE | 创建者 |

**ad_impressions**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `ad_id` | INT | FK→advertisements.id, CASCADE, INDEX | 广告 |
| `user_id` | INT | FK→users.id, INDEX | 用户 |
| `action` | VARCHAR(10) | NOT NULL, INDEX | view/click |
| `created_at` | TIMESTAMPTZ | NOT NULL | 时间 |

---

#### saved_searches（保存搜索表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `user_id` | INT | FK→users.id, CASCADE, INDEX | 用户 |
| `name` | VARCHAR(100) | NOT NULL | 搜索命名 |
| `query_params` | JSON | NOT NULL | 搜索条件 |
| `notify_enabled` | BOOLEAN | DEFAULT true | 是否推送 |
| `last_notified_at` | TIMESTAMPTZ | NULL | 上次推送时间 |

---

#### embedding_jobs（Embedding 任务表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `property_id` | INT | FK→properties.id, CASCADE, INDEX | 房源 |
| `status` | ENUM(pending,processing,completed,failed) | NOT NULL, DEFAULT pending | 状态 |
| `error_message` | TEXT | NULL | 错误信息 |
| `started_at` | TIMESTAMPTZ | NULL | 开始时间 |
| `completed_at` | TIMESTAMPTZ | NULL | 完成时间 |

---

#### data_imports（数据导入表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `admin_id` | INT | FK→users.id, CASCADE, INDEX | 操作人 |
| `source_name` | VARCHAR(255) | NOT NULL | 文件名 |
| `source_type` | ENUM(csv,excel,api) | NOT NULL | 来源类型 |
| `status` | ENUM(pending,processing,completed,failed) | NOT NULL, DEFAULT pending | 状态 |
| `total_records` | INT | NOT NULL, DEFAULT 0 | 总记录数 |
| `success_records` | INT | NOT NULL, DEFAULT 0 | 成功数 |
| `failed_records` | INT | NOT NULL, DEFAULT 0 | 失败数 |
| `error_log` | TEXT | NULL | 错误日志(JSON) |

---

#### audit_logs（审计日志表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, INDEX | 自增主键 |
| `user_id` | INT | FK→users.id, INDEX | 操作人 |
| `action` | VARCHAR(100) | NOT NULL, INDEX | 操作类型 |
| `resource_type` | VARCHAR(50) | INDEX | 资源类型 |
| `resource_id` | INT | NULL | 资源 ID |
| `details` | JSON | NULL | 详情 |
| `ip_address` | VARCHAR(45) | NULL | IP 地址 |
| `created_at` | TIMESTAMPTZ | NOT NULL | 操作时间 |

---

#### property_pois（房源周边设施表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | UUID(36) | PK | UUID 主键 |
| `property_id` | INT | FK→properties.id, CASCADE, UNIQUE, INDEX | 房源(一对一) |
| `content` | TEXT | NOT NULL | POI 文本描述 |
| `poi_data` | JSON | NULL | POI 结构化数据 |
| `generated_at` | TIMESTAMPTZ | NOT NULL | 生成时间 |
| `reviewed` | BOOLEAN | DEFAULT false | 已审核 |

---

## 三、API 端点设计（按页面/按钮映射）

### 3.1 映射说明

> 每个端点下方用 `→ 前端按钮/页面` 标注其对应的前端操作。

---

### 认证授权 `[auth]` → `/auth`

| 方法 | 路径 | 说明 | → 前端按钮/页面 |
|------|------|------|-----------------|
| `POST` | `/auth/register` | 用户注册 | 注册页 → "注册" 按钮 |
| `POST` | `/auth/login` | 用户名/邮箱登录 | 登录页 → "登录" 按钮 |
| `POST` | `/auth/refresh` | 刷新 Access Token | 前端拦截器 → Token 过期自动刷新 |
| `GET` | `/auth/me` | 获取当前用户信息 | 全局 → 导航栏用户头像/名称 |

---

### 微信集成 `[wechat]` → 无统一 prefix

| 方法 | 路径 | 说明 | → 前端按钮/页面 |
|------|------|------|------------------|
| `POST` | `/auth/wechat/login` | 微信小程序登录 | 小程序 → "微信一键登录" |
| `POST` | `/auth/wechat/phone` | 绑定微信手机号 | 小程序 → "获取手机号" |
| `GET` | `/wechat/config` | 获取微信配置(AppID) | 小程序初始化 |

---

### 用户管理 `[users]` → `/users`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `POST` | `/users` | 创建用户 | 管理后台 → "添加用户" | 公开(注册改用 /auth/register) |
| `GET` | `/users` | 用户列表(分页) | 管理后台 → 用户管理页 | admin |
| `GET` | `/users/me` | 当前用户资料 | 个人中心页 | 登录用户 |
| `PATCH` | `/users/me` | 修改个人资料 | 个人中心 → "保存" 按钮 | 登录用户 |
| `GET` | `/users/{user_id}` | 查看用户详情 | 管理后台 → 用户详情 | admin |
| `PATCH` | `/users/{user_id}` | 修改用户 | 管理后台 → 编辑用户 → "保存" | admin |
| `DELETE` | `/users/{user_id}` | 删除用户(软删除) | 管理后台 → "删除" 按钮 | admin |

---

### 房源管理 `[properties]` → `/properties`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `GET` | `/properties` | 房源列表(分页/筛选) | 首页 → 房源列表 | 公开 |
| `GET` | `/properties/search` | 语义搜索 | 首页 → 搜索框 | 公开 |
| `POST` | `/properties` | 发布房源 | 房东 → "发布房源" 按钮 | landlord |
| `GET` | `/properties/{id}` | 房源详情 | 房源详情页 | 公开 |
| `PATCH` | `/properties/{id}` | 编辑房源 | 房东 → "编辑" → "保存" | landlord |
| `DELETE` | `/properties/{id}` | 删除房源 | 房东 → "删除" 按钮 | landlord |

**搜索参数**：`q`(语义搜索)、`district`、`price_min`、`price_max`、`bedrooms`、`property_type`

---

### 图片管理 `[images]` → `/properties`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `GET` | `/properties/{id}/images` | 查看房源图片列表 | 房源详情页 → 图片轮播 | 公开 |
| `POST` | `/properties/{id}/images` | 上传图片(多文件) | 房东 → "上传图片" 按钮 | landlord |
| `DELETE` | `/properties/{id}/images/{image_id}` | 删除图片 | 房东 → 图片上的 "×" 删除 | landlord |
| `PATCH` | `/properties/{id}/images/{image_id}/primary` | 设为封面 | 房东 → "设为封面" 按钮 | landlord |

- 文件限制：JPEG/PNG/WebP，单个最大 5MB，每房源最多 10 张

---

### 预约看房 `[bookings]` → `/bookings`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `POST` | `/bookings` | 创建预约 | 房源详情页 → "预约看房" 按钮 | tenant |
| `GET` | `/bookings` | 我的预约列表 | 租客/房东 → "我的预约" 页 | 登录用户 |
| `GET` | `/bookings/{id}` | 预约详情 | 预约详情页 | 参与双方+admin |
| `PATCH` | `/bookings/{id}/status` | 房东审批预约 | 房东 → "同意"/"拒绝" 按钮(仅 approved/rejected) | landlord |
| `PATCH` | `/bookings/{id}/cancel` | 租客取消预约 | 租客 → "取消预约" 按钮 | tenant |

---

### 支付系统 `[payments]` → `/payments`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `POST` | `/payments/create` | 创建支付(发起微信支付) | 预约页 → "支付押金" 按钮 | tenant |
| `POST` | `/payments/{id}/callback` | 支付回调(模拟) | 微信支付回调 → 服务器自动触发 | 内部 |
| `GET` | `/payments/{id}` | 查询支付状态 | 支付结果页 | 付款人+admin |

---

### 电子合同 `[contracts]` → `/contracts`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `POST` | `/contracts/{booking_id}/generate` | 生成合同(基于模板) | 预约页 → "生成合同" 按钮 | 参与双方+admin |
| `GET` | `/contracts/{contract_id}` | 查看合同详情 | 合同详情页 | 参与双方+admin |
| `POST` | `/contracts/{contract_id}/sign` | 签署合同 | 合同页 → "签署" 按钮 | tenant |
| `GET` | `/contracts/{contract_id}/download` | 下载合同文本 | 合同页 → "下载" 按钮 | 参与双方+admin |

---

### 消息通知 `[notifications]` → `/notifications`

| 方法 | 路径 | 说明 | → 前端按钮/页面 |
|------|------|------|-----------------|
| `GET` | `/notifications` | 通知列表 | 导航栏 → 铃铛图标 → 通知列表 |
| `PATCH` | `/notifications/{id}/read` | 标记单条已读 | 通知列表 → 点击某条通知 |
| `PATCH` | `/notifications/read-all` | 全部标记已读 | 通知列表 → "全部已读" 按钮 |
| `GET` | `/notifications/unread-count` | 未读通知数 | 导航栏 → 铃铛角标数字 |

---

### AI 在线沟通 `[chat]` → `/chat`

| 方法 | 路径 | 说明 | → 前端按钮/页面 |
|------|------|------|-----------------|
| `POST` | `/chat/sessions` | 创建新会话 | 聊天页 → "新建对话" 按钮 |
| `GET` | `/chat/sessions` | 会话列表 | 聊天页 → 左侧会话列表 |
| `GET` | `/chat/sessions/{id}/messages` | 获取历史消息 | 聊天页 → 消息区域(进入时加载) |
| `POST` | `/chat/sessions/{id}/messages` | 发送消息(SSE 流式) | 聊天页 → 输入框 → "发送" 按钮 |
| `DELETE` | `/chat/sessions/{id}` | 删除会话 | 聊天页 → 会话 "删除" 按钮 |

---

### 地图服务 `[map]` → `/map`

| 方法 | 路径 | 说明 | → 前端按钮/页面 |
|------|------|------|-----------------|
| `GET` | `/map/properties` | 地图房源标记(支持视口过滤) | 地图页 → 地图标记加载 |
| `GET` | `/map/config` | 地图配置(高德 Key、中心点) | 地图页初始化 |

**视口参数**：`sw_lat`, `sw_lng`, `ne_lat`, `ne_lng`（地图拖拽/缩放时实时请求）

---

### 地理编码 `[geo]` → `/geo`

| 方法 | 路径 | 说明 | → 前端按钮/页面 |
|------|------|------|-----------------|
| `POST` | `/geo/geocode` | 地址 → 经纬度 | 房源发布页 → 填地址 → 自动回填坐标 |

请求体：`{ "address": "苏州工业园区...", "city": "苏州" }`  
响应：`{ "latitude": 31.xxx, "longitude": 120.xxx, "formatted_address": "..." }`

---

### 周边设施 `[pois]` → `/pois`

| 方法 | 路径 | 说明 | → 前端按钮/页面 |
|------|------|------|-----------------|
| `GET` | `/pois/{property_id}` | 查看周边 POI | 房源详情页 → "周边设施" tab |
| `POST` | `/pois/{property_id}/generate` | 生成周边 POI(AI+高德) | 房源详情页 → "刷新周边" 按钮 |

- 调用高德周边搜索 API（半径 2000m，每类最多 5 条）
- POI 内容缓存于 `property_pois` 表

---

### 数据导入 `[import]` → `/import`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `POST` | `/import/upload` | 上传 CSV/Excel 批量导入 | 管理后台 → "批量导入" 按钮 | admin |
| `GET` | `/import/tasks` | 导入任务列表 | 管理后台 → 导入历史页 | admin |
| `GET` | `/import/tasks/{id}` | 导入任务详情 | 管理后台 → 导入记录详情 | admin |
| `POST` | `/import/tasks/{id}/retry` | 重试失败记录 | 管理后台 → "重试" 按钮 | admin |

- 支持格式：CSV / Excel（最大 10MB）

---

### 管理后台 `[admin]` → `/admin`

| 方法 | 路径 | 说明 | → 前端按钮/页面 | 权限 |
|------|------|------|-----------------|------|
| `GET` | `/admin/stats` | 全局统计 | 管理后台 → 仪表盘 | admin |
| `GET` | `/admin/logs` | 审计日志列表 | 管理后台 → 操作日志页 | admin |
| `PATCH` | `/admin/properties/{id}/status` | 审核房源状态 | 管理后台 → 房源管理 → 状态变更 | admin |
| `PATCH` | `/admin/users/{id}/role` | 修改用户角色 | 管理后台 → 用户管理 → "修改角色" | admin |
| `GET` | `/admin/embeddings/stats` | Embedding 任务统计 | 管理后台 → Embedding 状态 | admin |
| `POST` | `/admin/embeddings/reindex` | 触发全量/单房源重建 Embedding | 管理后台 → "重建索引" 按钮 | admin |

---

### 系统健康 `[health]`

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |

---

## 四、架构分层

```
┌─────────────────────────────────────────────┐
│                 FastAPI App                  │
│  ┌───────────────────────────────────────┐  │
│  │         API Routes (路由层)             │  │
│  │  auth / users / properties / bookings  │  │
│  │  payments / contracts / chat / admin   │  │
│  │  geo / map / pois / import / wechat    │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │        Services (业务逻辑层)            │  │
│  │  AuthService, PropertyService,         │  │
│  │  BookingService, PaymentService,       │  │
│  │  ContractService, ChatService,         │  │
│  │  GeocodingService, POIService,         │  │
│  │  ImageService, ImportService,          │  │
│  │  NotificationService, EmbeddingService │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │        Models (数据模型层)              │  │
│  │  14 个 SQLAlchemy ORM 模型              │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │        Schemas (验证层)                 │  │
│  │  Pydantic v2 请求/响应 Schema           │  │
│  └───────────────────────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │     Core (基础设施)                     │  │
│  │  配置 / 安全 / 日志 / 监控 / 依赖注入    │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│              Celery Tasks (异步层)            │
│  embedding_tasks / import_tasks             │
│  notification_tasks / payment_tasks         │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│         PostgreSQL + Redis + Celery          │
└─────────────────────────────────────────────┘
```

---

## 五、认证与授权

### 5.1 JWT 双 Token 机制

| Token | 过期时间 | 用途 |
|-------|---------|------|
| Access Token | 60 分钟 | API 请求鉴权（`Authorization: Bearer <token>`） |
| Refresh Token | 7 天 | 刷新 Access Token（`POST /auth/refresh`） |

### 5.2 权限体系（RBAC）

| 角色 | 枚举值 | 权限范围 |
|------|--------|---------|
| 租客 | `tenant` | 搜索/查看房源、预约看房、支付、签合同、聊天 |
| 房东 | `landlord` | 发布/编辑/删除房源、确认预约、上传图片 |
| BD经理 | `bd_manager` | 录入公寓管理机构 |
| 管理员 | `admin` | 全局管理：用户管理、房源审核、数据导入、系统统计 |

### 5.3 依赖注入

| 依赖函数 | 说明 |
|---------|------|
| `get_db_session` | 注入异步数据库会话 |
| `get_current_user` | 从 JWT 解析当前用户（必须登录） |
| `require_tenant` | 要求租客角色 |
| `require_landlord` | 要求房东角色 |
| `require_admin` | 要求管理员角色 |

---

## 六、第三方集成

| 服务 | 用途 | 配置项 |
|------|------|--------|
| 高德地图 | 地理编码 + 周边 POI 搜索 + 前端 JS SDK | `AMAP_WEB_KEY`, `AMAP_GEOCODE_URL`, `AMAP_AROUND_URL` |
| OpenAI | 文本 Embedding（语义搜索）、GPT-4o（AI 聊天） | `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL` |
| 微信小程序 | 小程序登录（code2Session）、手机号绑定 | `WECHAT_APPID`, `WECHAT_SECRET` |
| 阿里云 SMS | 短信通知 | `SMS_ACCESS_KEY_ID`, `SMS_TEMPLATE_CODE` |
| SMTP | 邮件通知 | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` |
| Redis | Celery 消息队列 + 缓存 | `REDIS_URL` |

---

## 七、异步任务 (Celery)

| 任务模块 | 说明 |
|---------|------|
| `embedding_tasks` | 房源发布后异步生成 OpenAI Embedding 向量 |
| `import_tasks` | 异步批量导入 CSV/Excel 房源数据 |
| `notification_tasks` | 异步发送短信/邮件通知 |
| `payment_tasks` | 支付状态轮询/过期处理 |

---

##

## 八、数据字段与前后端接口连调设计

> 本章列出每个 API 的请求/响应 JSON 结构，前端开发者可按此定义 TypeScript 类型、编写 API 调用层，并进行联调验证。

---

### 8.1 认证模块

#### POST /auth/register — 注册

**请求体** (`RegisterRequest`)：
```json
{
  "username": "zhangsan",
  "password": "password123",
  "phone": "13800138000",
  "email": "zhangsan@example.com",
  "role": "tenant"
}
```

**响应体** (`CurrentUserResponse`)：
```json
{
  "id": 1,
  "username": "zhangsan",
  "phone": "13800138000",
  "wechat_openid": null,
  "email": "zhangsan@example.com",
  "role": "tenant",
  "status": "active",
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:00:00Z"
}
```

**错误码**：409 — username/email/phone 已存在

---

#### POST /auth/login — 登录

**请求体** (`LoginRequest`)：
```json
{
  "username_or_email": "zhangsan",
  "password": "password123"
}
```

**响应体** (`TokenResponse`)：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

> 前端需将 `access_token` 存入 localStorage，后续请求带 `Authorization: Bearer <token>` 头。  
> Token 过期时调用 `POST /auth/refresh` 用 Refresh Token 换取新 Token。

**错误码**：401 — 用户名或密码错误

---

#### GET /auth/me — 当前用户信息

**响应体**：同注册返回的 `CurrentUserResponse`

**错误码**：401 — 未登录或 Token 过期

---

### 8.2 房源模块

#### GET /properties — 房源列表

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `skip` | int | 否 | 分页偏移(默认 0) |
| `limit` | int | 否 | 每页数量(1-100, 默认 20) |
| `district` | string | 否 | 区域筛选 |
| `status` | string | 否 | 状态筛选 |

**响应体** (`list[PropertyRead]`)：
```json
[
  {
    "id": 1,
    "landlord_id": 2,
    "title": "园区湖东精装两室",
    "description": "交通便利，近地铁...",
    "address": "苏州工业园区湖东XX路XX号",
    "district": "工业园区",
    "price_monthly": "3500.00",
    "area_sqm": "85.50",
    "bedrooms": 2,
    "bathrooms": 1,
    "property_type": "apartment",
    "status": "available",
    "latitude": "31.322000",
    "longitude": "120.720000",
    "deposit_amount": 1000,
    "service_fee_rate": 0.10,
    "created_at": "2026-06-20T08:00:00Z",
    "updated_at": "2026-06-20T08:00:00Z",
    "images": [
      {
        "id": 1,
        "property_id": 1,
        "filename": "abc123.jpg",
        "original_name": "客厅.jpg",
        "mime_type": "image/jpeg",
        "file_size": 204800,
        "sort_order": 0,
        "is_primary": true,
        "created_at": "2026-06-20T08:00:00Z"
      }
    ]
  }
]
```

> `price_monthly` 为 `Decimal` 类型，前端展示时需格式化为两位小数。经纬度在有地理编码后才回填。

---

#### GET /properties/search — 语义搜索

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `q` | string | 否 | 自然语言搜索 |
| `district` | string | 否 | 区域筛选 |
| `price_min` | decimal | 否 | 最低租金 |
| `price_max` | decimal | 否 | 最高租金 |
| `bedrooms` | int | 否 | 卧室数 |
| `property_type` | string | 否 | 房源类型 |
| `limit` | int | 否 | 数量(1-100, 默认 20) |

**响应体** (`list[PropertySearchResult]`)：与 `PropertyRead` 结构相同，额外包含 `similarity` 字段表示语义匹配度 (0~1)。

---

#### POST /properties — 发布房源

**请求体** (`PropertyCreate`)：
```json
{
  "landlord_id": 2,
  "title": "园区湖东精装两室",
  "description": "交通便利，近地铁...",
  "address": "苏州工业园区湖东XX路XX号",
  "district": "工业园区",
  "price_monthly": "3500.00",
  "area_sqm": "85.50",
  "bedrooms": 2,
  "bathrooms": 1,
  "property_type": "apartment",
  "status": "available",
  "latitude": null,
  "longitude": null,
  "deposit_amount": 1000,
  "service_fee_rate": 0.10
}
```

**响应体**：返回创建的 `PropertyRead`，201 Created

> **联调要点**：
> 1. 发布成功后，前端应立即引导房东上传图片（`POST /properties/{id}/images`）
> 2. 后端异步触发地理编码 + Embedding 生成，经纬度会在几秒内回填
> 3. 房东只能为自己创建房源，`landlord_id` 必须 = 当前登录用户 ID

**错误码**：403 — 非房东/管理员；422 — landlord_id 不存在

---

#### PATCH /properties/{id} — 编辑房源

**请求体** (`PropertyUpdate`)：所有字段均为可选，只更新传入的字段。
```json
{
  "title": "园区湖东精装两室(降价)",
  "price_monthly": "3200.00"
}
```

**响应体**：更新后的 `PropertyRead`

---

#### DELETE /properties/{id} — 删除房源

**响应**：204 No Content（无响应体）

---

### 8.3 图片模块

#### POST /properties/{id}/images — 上传图片

**请求**：`multipart/form-data`，字段名 `files`（可多文件）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `files` | File[] | 是 | 图片文件列表 |

**限制**：JPEG/PNG/WebP，单文件 ≤ 5MB，每房源 ≤ 10 张

**响应体** (`list[PropertyImageRead]`)：
```json
[
  {
    "id": 1,
    "property_id": 1,
    "filename": "abc123.jpg",
    "original_name": "客厅.jpg",
    "mime_type": "image/jpeg",
    "file_size": 204800,
    "sort_order": 0,
    "is_primary": true,
    "created_at": "2026-06-26T10:00:00Z"
  }
]
```

> 图片访问路径：`/api/v1/uploads/{filename}`

---

#### PATCH /properties/{id}/images/{image_id}/primary — 设为封面

**响应体**：更新后的 `PropertyImageRead`（该房源其他图片 `is_primary` 自动设为 false）

---

#### DELETE /properties/{id}/images/{image_id} — 删除图片

**响应**：204 No Content

---

### 8.4 预约模块

#### POST /bookings — 创建预约

**请求体** (`BookingCreate`)：
```json
{
  "property_id": 1,
  "message": "我想周六下午看房",
  "scheduled_date": "2026-06-28 14:00"
}
```

> `message` 和 `scheduled_date` 至少填一个

**响应体** (`BookingRead`)：
```json
{
  "id": 1,
  "tenant_id": 3,
  "property_id": 1,
  "landlord_id": 2,
  "status": "pending",
  "message": "我想周六下午看房",
  "scheduled_date": "2026-06-28 14:00",
  "deposit_amount": 1000,
  "service_fee": 100,
  "deposit_status": "unpaid",
  "payment_transaction_id": null,
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:00:00Z"
}
```

**错误码**：400 — message & scheduled_date 都为空；404 — 房源不存在；409 — 已有待处理预约

---

#### GET /bookings — 我的预约列表

**响应体** (`list[BookingRead]`)

> **联调要点**：租客登录返回自己的预约；房东/管理员登录返回名下房源的预约

---

#### PATCH /bookings/{id}/status — 房东审批

**请求体** (`BookingUpdate`)：
```json
{
  "status": "approved"
}
```

> 仅允许 `approved` 或 `rejected`

**响应体**：更新后的 `BookingRead`

**错误码**：400 — 状态值非法；403 — 非该房源房东

---

#### PATCH /bookings/{id}/cancel — 租客取消

**无请求体**。预约状态变为 `cancelled`。

---

### 8.5 支付模块

#### POST /payments/create — 发起支付

**请求体** (`PaymentCreate`)：
```json
{
  "booking_id": 1,
  "amount": 1000
}
```

> `amount` 单位为分（如 1000 = 10.00 元）

**响应体** (`PaymentResponse`)：
```json
{
  "id": "a1b2c3d4-...",
  "booking_id": 1,
  "user_id": 3,
  "amount": 1000,
  "transaction_id": "a1b2c3d4e5f6...",
  "status": "pending",
  "payment_method": "wechat_pay",
  "paid_at": null,
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:00:00Z"
}
```

> **联调要点**：创建支付后，前端需调起微信支付（获取 `transaction_id`）。支付完成后微信回调 `POST /payments/{id}/callback`，将 status 更新为 `success`。

---

#### GET /payments/{id} — 查询支付

**响应体**：`PaymentResponse`（含最新 status）

> **联调要点**：前端支付完成后，轮询此接口确认支付状态变更。

---

### 8.6 合同模块

#### POST /contracts/{booking_id}/generate — 生成合同

**无请求体**。基于标准模板 + 预约/房源信息自动填充。

**响应体** (`ContractResponse`)：
```json
{
  "id": "e5f6a7b8-...",
  "booking_id": 1,
  "tenant_id": 3,
  "property_id": 1,
  "template_name": "standard_lease",
  "content": "房屋租赁合同\n\n甲方(出租方)：...",
  "status": "draft",
  "signed_at": null,
  "file_path": null,
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:00:00Z"
}
```

**错误码**：409 — 该预约已生成过合同

---

#### POST /contracts/{contract_id}/sign — 签署合同

**无请求体**。合同状态变为 `signed`，记录 `signed_at`。

**错误码**：403 — 只有租客可签署；409 — 已签署

---

#### GET /contracts/{contract_id}/download — 下载合同

**响应**：`text/plain; charset=utf-8`，合同纯文本内容。

---

### 8.7 通知模块

#### GET /notifications — 通知列表

**响应体** (`list[NotificationRead]`)：
```json
[
  {
    "id": 1,
    "user_id": 3,
    "type": "booking_approved",
    "title": "预约已确认",
    "content": "您的看房预约已被房东确认",
    "is_read": false,
    "created_at": "2026-06-26T10:00:00Z",
    "updated_at": "2026-06-26T10:00:00Z"
  }
]
```

---

#### GET /notifications/unread-count — 未读数

**响应体** (`UnreadCount`)：
```json
{ "count": 3 }
```

> **联调要点**：前端在导航栏轮询此接口（如每 30s），更新铃铛角标。

---

#### PATCH /notifications/{id}/read — 标记已读

**响应体**：更新后的 `NotificationRead`（`is_read: true`）

---

#### PATCH /notifications/read-all — 全部已读

**响应体**：`{ "detail": "All notifications marked as read" }`

---

### 8.8 聊天模块

#### POST /chat/sessions — 创建会话

**请求体**：
```json
{ "title": "咨询房源#1" }
```

**响应体** (`SessionResponse`)：
```json
{
  "id": 1,
  "session_id": "abc123...",
  "title": "咨询房源#1",
  "status": "active",
  "created_at": "2026-06-26T10:00:00+00:00",
  "updated_at": "2026-06-26T10:00:00+00:00"
}
```

---

#### POST /chat/sessions/{id}/messages — 发送消息 (SSE 流式)

**请求体**：
```json
{ "content": "这个房源离地铁站多远？" }
```

**响应**：`text/event-stream`（Server-Sent Events），逐 token 流式返回 AI 回复。

```
data: {"role":"assistant","content":"根据"}
data: {"role":"assistant","content":"地图"}
data: {"role":"assistant","content":"数据"}
...
data: [DONE]
```

> **联调要点**：前端使用 `EventSource` 或 `fetch` + `ReadableStream` 消费 SSE。结束后需刷新消息列表展示完整对话。

---

### 8.9 地图 & 地理编码

#### POST /geo/geocode — 地址转经纬度

**请求体** (`GeocodeRequest`)：
```json
{
  "address": "苏州工业园区仁爱路111号",
  "city": "苏州"
}
```

**响应体** (`GeocodeResponse`)：
```json
{
  "address": "苏州工业园区仁爱路111号",
  "latitude": "31.274500",
  "longitude": "120.738200",
  "formatted_address": "江苏省苏州市工业园区仁爱路111号",
  "level": "门牌号",
  "province": "江苏省",
  "city": "苏州市",
  "district": "工业园区"
}
```

> **联调要点**：房源发布时，填完地址后可调用此接口自动回填经纬度到表单。

---

#### GET /map/properties — 地图房源标记

**Query 参数**：`sw_lat`, `sw_lng`, `ne_lat`, `ne_lng`（视口边界）

**响应体**：
```json
{
  "count": 42,
  "items": [
    {
      "id": 1,
      "title": "园区湖东精装两室",
      "district": "工业园区",
      "address": "苏州工业园区...",
      "price_monthly": "3500.00",
      "bedrooms": 2,
      "bathrooms": 1,
      "property_type": "apartment",
      "latitude": 31.322,
      "longitude": 120.72,
      "area_sqm": "85.50"
    }
  ]
}
```

> **联调要点**：前端地图每次拖拽/缩放时，用当前视口边界调用此接口刷新标记点。

---

#### GET /map/config — 地图配置

**响应体**：
```json
{
  "amap_js_key": "your-amap-key",
  "center": [39.9042, 116.4074],
  "zoom": 11
}
```

---

### 8.10 周边设施 (POI)

#### GET /pois/{property_id} — 查看周边

**响应体** (`POIResponse`)：
```json
{
  "id": "uuid-...",
  "property_id": 1,
  "content": "## 周边交通\n- 地铁1号线(星湖街站) 步行8分钟\n...",
  "poi_data": {
    "transport": [],
    "education": [],
    "healthcare": []
  },
  "generated_at": "2026-06-26T10:00:00Z",
  "reviewed": false,
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:00:00Z"
}
```

> **联调要点**：首次访问时自动触发生成（调用高德周边搜索），后续命中缓存。

---

### 8.11 数据导入 (admin)

#### POST /import/upload — 批量导入

**请求**：`multipart/form-data`，字段名 `file`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | CSV 或 Excel，≤ 10MB |

**响应体**：
```json
{
  "id": 1,
  "source_name": "房源数据.csv",
  "source_type": "csv",
  "status": "completed",
  "total_records": 200,
  "success_records": 195,
  "failed_records": 5,
  "created_at": "2026-06-26T10:00:00+00:00"
}
```

---

### 8.12 前端联调检查清单

| 检查项 | 说明 |
|--------|------|
| Token 管理 | localStorage 存储，请求拦截器自动附加 `Authorization: Bearer` |
| 401 处理 | Token 过期 → 自动调 `/auth/refresh`，失败则跳转登录页 |
| 403 处理 | 权限不足 → Toast 提示，不展示越权按钮 |
| Decimal 序列化 | 金额、经纬度、面积等 `Decimal` 字段在前端为字符串，需 `parseFloat()` |
| 图片访问 | 路径拼接：`{API_BASE}/uploads/{filename}` |
| SSE 流式 | 聊天使用 EventSource + 手动拼接回复 |
| 地图视口 | 防抖 500ms 后再请求 `/map/properties` |
| 文件上传 | `multipart/form-data`，字段名严格匹配 `files` / `file` |
| 轮询策略 | 未读通知：30s 间隔；支付状态：2s 间隔(最多 30 次) |

---

## 九、部署架构图

### 9.1 Docker Compose 服务拓扑

```
                    Internet
                        │
                        ▼
             ┌──────────────────┐
             │   Nginx :80      │  ← 前端 SPA 静态文件
             │   (frontend)      │  ← API 反向代理 /api/* → backend:8000
             └────────┬─────────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
     frontend     backend      (隔离)
     (外网)       (内网)        data
                      │           │
             ┌────────▼─────────┐ │
             │  FastAPI :8000   │ │
             │  (backend)       │ │
             │  gunicorn 4wk    │ │
             └────────┬─────────┘ │
                      │           │
        ┌─────────────┼─────┐     │
        │             │     │     │
   ┌────▼────┐ ┌──────▼──┐ │     │
   │ Celery  │ │ Celery  │ │     │
   │ Worker  │ │ Beat    │ │     │
   │(4 proc) │ │(scheduler)│    │
   └────┬────┘ └─────────┘ │     │
        │                  │     │
        └──────────────────┘     │
                 │               │
        ┌────────▼───────┐  ┌───▼──────────┐
        │  Redis :6379   │  │ PostgreSQL:5432│
        │  (队列+缓存)    │  │  (pgvector)    │
        └────────────────┘  └───────────────┘
```

### 9.2 服务清单

| 服务 | 容器名 | 端口 | 职责 |
|------|--------|------|------|
| **Nginx** | `rental_nginx` | 80 | 前端 SPA 托管 + `/api/*` 反向代理到 backend:8000 |
| **FastAPI** | `rental_backend` | 8000 (内网) | REST API，gunicorn 4 worker |
| **Celery Worker** | `rental_celery_worker` | — | 异步任务：Embedding、导入、通知、支付 |
| **Celery Beat** | `rental_celery_beat` | — | 定时任务调度（如过期支付清理） |
| **PostgreSQL** | `rental_postgres` | 5432 (内网) | 主数据库 + pgvector 扩展 |
| **Redis** | `rental_redis` | 6379 (内网) | Celery Broker + 缓存 |

### 9.3 网络隔离（三层网络）

| 网络 | 类型 | 接入服务 | 说明 |
|------|------|---------|------|
| `frontend` | bridge (外网可达) | Nginx | 仅 Nginx 暴露 80 端口 |
| `backend` | bridge (internal) | Nginx, FastAPI, Celery, Celery Beat | API 层互访，外网不可达 |
| `data` | bridge (internal) | FastAPI, Celery, PostgreSQL, Redis | 数据层互访，外网不可达 |

> **安全原则**：数据库和 Redis 不暴露宿主机端口，仅通过 `data` 内网被后端服务访问。

### 9.4 数据流路径

```
用户浏览器
  │  GET /                  → Nginx → 返回 Vue SPA (index.html)
  │  GET /api/v1/properties → Nginx → proxy_pass → FastAPI → PostgreSQL → JSON
  │  POST /api/v1/properties/{id}/images → Nginx → FastAPI → 存磁盘 + DB 记录
  │  POST /chat/sessions/{id}/messages → Nginx → FastAPI → OpenAI API (SSE 转发)
  │
后端内部:
  │  [房源发布] → FastAPI → Celery Worker → OpenAI Embedding API → PostgreSQL
  │  [数据导入] → FastAPI → Celery Worker → 解析 CSV/Excel → PostgreSQL
  │  [定时任务] → Celery Beat → 触发 Celery Worker → 支付过期检查/通知清理
```

### 9.5 启动命令

```bash
# 开发环境
docker compose up -d
cd backend && python run_dev.py   # FastAPI 热重载

# 生产环境
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### 9.6 关键环境变量

| 变量 | 用途 | 示例 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接 | `postgresql+asyncpg://user:pass@postgres:5432/rental_housing` |
| `REDIS_URL` | Redis 连接 | `redis://:password@redis:6379/0` |
| `AUTH_SECRET_KEY` | JWT 签名密钥 | 生产环境使用 64 位随机字符串 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-...` |
| `AMAP_WEB_KEY` | 高德地图 Web API Key | — |
| `WECHAT_APPID` | 微信小程序 AppID | — |
| `ENVIRONMENT` | 运行环境 | `production` / `development` |

---

## 十、Alembic 迁移历史

| 版本 | 文件 | 内容 |
|------|------|------|
| 0001 | `20260617_0001_initial_users_properties.py` | 初始：users + properties |
| 0002 | `20260620_0002_pgvector_embedding.py` | pgvector extension + embedding 字段 |
| 0003 | `20260620_0003_property_images.py` | property_images 表 |
| 0004 | `20260620_0004_booking_and_notification.py` | bookings + notifications 表 |
| 0005 | `20260620_0005_embedding_jobs_and_audit_logs.py` | embedding_jobs + audit_logs |
| 0006 | `20260622_0006_chat_tables.py` | chat_sessions + chat_messages |
| 0007 | `20260622_0007_data_import.py` | data_imports 表 |
| 0008 | `20260623_0008_deposit_contract_payment_poi.py` | 押金字段 + contracts + payments + property_pois |
| 0009 | `20260624_0009_extend_notification_type_enum.py` | 扩展通知类型枚举 |
| 0010 | `20260626_0010_institutes_v15_v2.py` | institutes 表 + reviews 表 + 房源关联 institute |
| 0011 | `5ac4aa5f38f4_merge_migration_heads_after_ui_branch_.py` | 合并 UI 重构分支的多头迁移（地图找房 + 机构/市场/广告/评论） |

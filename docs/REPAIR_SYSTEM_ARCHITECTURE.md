# 维修工单系统 — 底层架构与字段表格

> 负责人：Riki1124-  
> 分支：`feat/repair-request-and-user-page`

---

## 一、系统架构

### 1.1 技术栈
```
前端：Vue 3 + TypeScript + Element Plus + Pinia
后端：FastAPI + SQLAlchemy 2.0 (async) + Pydantic
数据库：PostgreSQL 16 + pgvector
通信：RESTful API + Axios + Vite Proxy
```

### 1.2 系统分层架构

```
┌─────────────────────────────────────────────────┐
│                  前端 (Vue 3)                     │
│  views/ (页面)  →  stores/ (状态)  →  services/  │
│                                    (Axios HTTP)  │
├─────────────────────────────────────────────────┤
│                  后端 (FastAPI)                   │
│  routes/ (路由层) → services/ (业务逻辑)          │
│                   → models/  (ORM 模型)           │
│                   → schemas/ (Pydantic 验证)      │
├─────────────────────────────────────────────────┤
│              数据库 (PostgreSQL)                  │
│  repair_requests  +  repair_workers               │
│  users  +  properties  +  bookings                │
└─────────────────────────────────────────────────┘
```

### 1.3 核心流程图

```
                     租客报修
                        │
                        ▼
              检测房东是否有维修工？
              ┌─────────┴─────────┐
              YES                  NO
              │                    │
              ▼                    ▼
       status = pending    status = pending_escalated
              │                    │
      房东派单(apartment)    Admin派单(platform)
              │                    │
              └────────┬───────────┘
                       ▼
              status = assigned
                       │
                 维修师傅开始工作
                       │
                       ▼
              status = in_progress
                       │
                 维修师傅完成
                       │
                       ▼
              status = completed
                       │
                  租客确认修好
                       │
                       ▼
              status = confirmed ✓
```

---

## 二、数据库字段表格

### 2.1 repair_requests（报修工单表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| `id` | INTEGER | PK, AUTO | 工单编号 |
| `property_id` | INTEGER | FK→properties.id, CASCADE | 关联房源 |
| `tenant_id` | INTEGER | FK→users.id, CASCADE | 报修租客 |
| `landlord_id` | INTEGER | FK→users.id, CASCADE | 房源房东 |
| `assigned_worker_id` | INTEGER | FK→users.id, SET NULL | 被指派维修工 |
| `issue_type` | ENUM | NOT NULL | 问题类型（见下表） |
| `description` | TEXT | NOT NULL | 问题描述 |
| `images` | JSON | NULLABLE | 报修图片URL数组 |
| `status` | ENUM | NOT NULL, INDEX | 工单状态（见下表） |
| `scheduled_time` | VARCHAR(32) | NULLABLE | 预约上门时间 |
| `completed_at` | VARCHAR(32) | NULLABLE | 维修完成时间 |
| `work_record` | TEXT | NULLABLE | 维修记录（师傅填写） |
| `work_images` | JSON | NULLABLE | 维修后照片URL数组 |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

### 2.2 repair_workers（维修师傅表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| `id` | INTEGER | PK, AUTO | 师傅编号 |
| `user_id` | INTEGER | FK→users.id, UNIQUE, CASCADE | 关联用户账号 |
| `manager_id` | INTEGER | FK→users.id, CASCADE | 所属管理者 |
| `status` | ENUM | NOT NULL, DEFAULT available | 工作状态（见下表） |
| `scope` | ENUM | NOT NULL, DEFAULT apartment | 归属范围（见下表） |
| `skills` | JSON | NULLABLE | 技能标签数组 |
| `phone` | VARCHAR(32) | NOT NULL | 联系电话 |
| `total_jobs` | INTEGER | DEFAULT 0 | 累计完成工单数 |
| `rating` | FLOAT | DEFAULT 5.0 | 评分（1-5） |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

### 2.3 枚举值定义

**issue_type（问题类型）：**

| 值 | 中文 |
|------|------|
| `plumbing` | 水电 |
| `appliance` | 家电 |
| `carpentry` | 门窗 |
| `wall_floor` | 墙面地面 |
| `plumbing_fixture` | 管道 |
| `other` | 其他 |

**status（工单状态）：**

| 值 | 中文 | 说明 |
|------|------|------|
| `pending` | 待处理 | 租客刚提交，等待房东处理 |
| `pending_escalated` | 待后台派单 | 房东无工人，跳过房东，等待Admin分配 |
| `assigned` | 已派单 | 已指派维修师傅 |
| `in_progress` | 维修中 | 师傅已开始工作 |
| `completed` | 待确认 | 师傅已完工，等待租客确认 |
| `confirmed` | 已确认 | 租客确认修好，工单关闭 |
| `rejected` | 已拒绝 | 房东拒绝此报修 |
| `cancelled` | 已取消 | 租客取消报修 |

**worker_status（维修工状态）：**

| 值 | 中文 | 说明 |
|------|------|------|
| `available` | 可调度 | 空闲，可接收新工单 |
| `working` | 工作中 | 有工单在进行 |
| `on_leave` | 休假中 | 管理者设为休假 |

**worker_scope（归属范围）：**

| 值 | 中文 | 说明 |
|------|------|------|
| `platform` | 网站管理 | Admin创建，对所有房东可见 |
| `apartment` | 公寓管理 | 房东创建，仅该房东可见 |

---

## 三、API 接口设计

### 3.1 报修接口（/api/v1/repairs）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/repairs` | tenant | 创建报修（自动检测房东是否有工人） |
| GET | `/repairs` | all (角色过滤) | 列表（租客看自己/房东看房源/师傅看分配） |
| GET | `/repairs/{id}` | 参与者 | 工单详情 |
| PATCH | `/repairs/{id}/status` | landlord/admin | 审批/拒绝 |
| PATCH | `/repairs/{id}/assign` | landlord/admin | 指派维修师傅 |
| PATCH | `/repairs/{id}/start` | maintenance_worker | 开始维修 |
| PATCH | `/repairs/{id}/complete` | maintenance_worker | 完成并写记录 |
| PATCH | `/repairs/{id}/cancel` | tenant | 租客取消 |
| PATCH | `/repairs/{id}/confirm` | tenant | 租客确认完工 |

### 3.2 维修师傅接口（/api/v1/repair-workers）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/repair-workers` | landlord/admin | 创建维修师傅 |
| GET | `/repair-workers` | landlord/admin | 列表（按scope过滤） |
| PATCH | `/repair-workers/{id}/status` | landlord/admin | 调整状态（含休假） |

### 3.3 数据台接口

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/landlord/dashboard` | landlord | 房东数据台 |
| GET | `/maintenance/dashboard` | maintenance_worker | 师傅数据台 |
| GET | `/admin/landlord-workers-status` | admin | 房东维修工看板 |

---

## 四、核心业务逻辑

### 4.1 智能路由（create_repair）

```python
# 创建报修时自动检测
if 房东有 apartment 维修工:
    status = "pending"          # 正常流程，房东自己处理
else:
    status = "pending_escalated"  # 跳过房东，通知Admin处理
```

### 4.2 派单范围控制（list_workers）

```python
# 房东只能看到自己的工人（不含platform）
if 当前用户是 landlord:
    return 自己创建的 apartment 工人
if 当前用户是 admin:
    return 所有工人（含platform）
```

### 4.3 角色权限矩阵

| 操作 | 租客 | 房东 | 维修师傅 | Admin |
|------|:--:|:--:|:--:|:--:|
| 创建报修 | ✅ | — | — | — |
| 取消报修 | ✅ | — | — | — |
| 确认完工 | ✅ | — | — | — |
| 查看自有房源报修 | — | ✅ | — | — |
| 派单给自有工人 | — | ✅ | — | — |
| 管理自有工人 | — | ✅ | — | — |
| 接收+完成工单 | — | — | ✅ | — |
| 查看已分配工单 | — | — | ✅ | — |
| 派单给任意工人 | — | — | — | ✅ |
| 查看全部工单 | — | — | — | ✅ |
| 查看房东工人看板 | — | — | — | ✅ |

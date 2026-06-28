# 2026-06-28 开发改动与遗留问题

## 一、今天改了什么

### 1. 支付流程修正

- 修正了押金支付状态流转。
  - 原来：创建支付单后直接把预约押金标成已支付。
  - 现在：创建支付单时标记为 `paying`，模拟支付回调成功后才标记为 `confirmed`。
- 新增/补齐支付网关字段：
  - `out_trade_no`
  - `prepay_id`
  - `trade_state`
  - `trade_state_desc`
- 增加支付状态枚举 `PaymentStatus`，方便后续接真实微信支付。
- 新增数据库迁移：
  - `backend/alembic/versions/20260628_0011_payment_gateway_fields.py`

### 2. 合同流程接入后端

- `ContractView.vue` 不再由前端静态拼合同内容，改为读取后端合同接口。
- 支持以下流程：
  - 根据预约生成合同。
  - 通过合同 ID 查看合同。
  - 签署合同。
  - 下载合同文本。
- 后端新增通过预约 ID 查询合同的接口：
  - `GET /api/v1/contracts/by-booking/{booking_id}`
- 合同生成逻辑调整为幂等：同一个预约已经有合同时，直接返回已有合同，不再报冲突。

### 3. 运营工作台接真实数据

- `AdminWorkspace.vue` 中的房源管理和预约管理改为读取真实后端数据。
- 支持运营端对预约执行：
  - 确认预约。
  - 驳回预约。
  - 标记已接待。
- 后端预约状态接口允许把已确认预约标记为 `completed`。
- 批量上架、批量下架、批量提醒等后端暂未提供接口的功能，前端改为明确提示“接口暂未开放”。

### 4. 收藏、报修、评价处理

- 收藏功能改为本地可用版本，使用 `localStorage` 保存收藏房源 ID。
- 个人中心收藏页不再拿普通房源列表冒充收藏列表。
- 报修功能改为本地记录版本，提交后写入 `localStorage`。
- 房源详情页移除了静态模拟评价，不再展示假评论。
- 评价区保留结构，但暂无真实评价数据时展示空状态。

### 5. 前端路由和鉴权优化

- 删除重复的 `property/:id/edit` 路由配置。
- 修正角色守卫：
  - 之前用户信息缺失但有 token 时，可能放过房东/管理员路由。
  - 现在缺失用户角色信息时会拦截对应权限路由。
- 登录流程优化：
  - 不再临时把空用户对象写入本地状态。
  - 先保存 token，再请求当前用户资料。

### 6. 地图、微信、地理编码修复

- 修复地图配置接口引用不存在的 `settings.amap_api_key` 问题。
- 修复微信手机号绑定接口中错误的 `await resp.json()`。
- 修复地理编码返回类型：
  - 经纬度由 `Decimal`/字符串改为 `float`，前后端和测试都按数字处理。
- 修复 `MapSearch.vue` 中 Leaflet 对象被 Vue 深层代理导致的 TypeScript 类型问题。

### 7. 配置和依赖补齐

- 补充微信支付相关环境变量：
  - `.env.example`
  - `.env.prod`
  - `backend/.env.example`
- `backend/requirements.txt` 补充 `cryptography`，用于微信支付签名相关逻辑。
- 测试环境下 Celery eager 模式不再触发真实微信/短信/邮件外部通知任务，只保留数据库通知记录，避免异步 coroutine warning。

## 二、目前还有的问题

### 1. 真实微信支付还没有完全接通

当前本地流程使用模拟支付回调，字段和配置已经补齐，但真实微信支付还需要：

- 商户号。
- API v3 key。
- 商户证书序列号。
- 商户私钥。
- 微信支付回调地址。
- 微信平台证书验签逻辑完善。

### 2. 支付宝没有后端接口

前端支付页已经移除了支付宝入口。后续如果要支持支付宝，需要补：

- 支付宝下单接口。
- 支付宝回调接口。
- 支付状态查询。
- 对应前端支付参数处理。

### 3. 收藏、报修还只是本地功能

目前收藏和报修用 `localStorage` 暂存，适合演示和前端流程联调，但不适合正式上线。

后续建议新增：

- 收藏表/API：
  - 收藏房源。
  - 取消收藏。
  - 我的收藏列表。
- 报修表/API：
  - 提交报修。
  - 查看报修进度。
  - 房东/运营方派单、完成、上传凭证。

### 4. 评价功能只有模型，没有完整接口

后端已有 `Review` 模型，但前端没有真实评价接口可用。

后续建议补：

- 创建评价。
- 房源/机构评价列表。
- 管理员审核评价。
- 评分统计。

### 5. 运营工作台仍有部分模块是展示性质

已经接入真实数据的模块：

- 房源管理。
- 预约管理。

仍偏展示/待接口补齐的模块：

- 合约管理批量操作。
- 财务中心。
- 租客管理。
- 维修工单。
- 消息中心。
- 门店设置。

### 6. 前端单元测试依赖缺失

`package.json` 中有 `vitest` 脚本，但依赖里没有安装：

- `vitest`
- `@vue/test-utils`
- `jsdom`

所以目前前端单元测试无法直接运行。因为项目原本使用 `package-lock.json`，本次没有用 `pnpm` 去改锁文件，避免混用包管理器。

### 7. 仍有第三方库 warning

后端测试已通过，但还有 2 个第三方库 warning：

- `python_multipart` 导入弃用提示。
- `passlib` 使用 Python `crypt` 的弃用提示。

这些不是本次代码逻辑错误，但后续升级依赖时可以处理。

## 三、验证结果

### 后端

```bash
cd backend
.venv/bin/python -m pytest -q
```

结果：

```text
76 passed, 10 skipped, 2 warnings
```

### 前端类型检查

```bash
cd frontend
PATH=/Users/shenjack/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/vue-tsc --noEmit
```

结果：通过。

### 前端生产构建

```bash
cd frontend
PATH=/Users/shenjack/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/vite build
```

结果：通过。

### Diff 检查

```bash
git diff --check
```

结果：通过。

## 四、涉及的主要文件

### 后端

- `backend/app/api/v1/routes/payments.py`
- `backend/app/api/v1/routes/contracts.py`
- `backend/app/api/v1/routes/bookings.py`
- `backend/app/models/payment.py`
- `backend/app/schemas/payment.py`
- `backend/app/services/contract_service.py`
- `backend/app/services/booking_service.py`
- `backend/app/services/notification_service.py`
- `backend/app/services/geocoding_service.py`
- `backend/app/core/config.py`
- `backend/alembic/versions/20260628_0011_payment_gateway_fields.py`

### 前端

- `frontend/src/views/DepositPayment.vue`
- `frontend/src/views/ContractView.vue`
- `frontend/src/views/AdminWorkspace.vue`
- `frontend/src/views/Profile.vue`
- `frontend/src/views/PropertyDetail.vue`
- `frontend/src/views/MapSearch.vue`
- `frontend/src/router/index.ts`
- `frontend/src/stores/auth.ts`
- `frontend/src/services/payment.ts`
- `frontend/src/services/contract.ts`
- `frontend/src/services/booking.ts`

### 配置

- `.env.example`
- `.env.prod`
- `backend/.env.example`
- `backend/requirements.txt`

# 团队分工文档

> 租房平台 · 6 人团队 · 最后更新 2026-07-06

---

## 一、分工总览

| 成员 | 板块 | 职责一句话 |
|------|------|-----------|
| lu-sir1219 | 房源信息设计与展示 | 房源 CRUD、详情页、搜索页、图片管理 |
| Michael9047 | 消息通知 | 站内信、短信、邮件通知 |
| shen25308 | 主页搜索流设计 | 首页 AI 对话搜索 + 购物车对比流 |
| Riki-1124 | 维修实现 | 报修申请、维修跟踪、评价反馈 |
| renwc | 系统管理员角色设计 | RBAC 权限、后台管理、用户管理 |
| JiaWu1211 | 支付流程完善 | 押金/租金支付、预约、合同签署 |

---

## 二、详细职责

### lu-sir1219 — 房源信息设计与展示
- 房源 CRUD（创建、编辑、删除、列表）
- 房源详情页设计
- 房源搜索页（传统过滤搜索）
- 首页房源展示
- PropertyCard 组件
- 图片上传与管理
- 数据导入

### Michael9047 — 消息通知
- 站内信通知系统
- 短信通知（阿里云 SMS）
- 邮件通知（SMTP）
- 通知模板管理
- 通知触发（预约提醒、支付通知等）

### shen25308 — 主页搜索流设计
- AI 智能对话搜索
- 地图找房（视口框选 + 聚合）
- 搜索首页 redesign
- 购物车对比流（后续）
- LLM 服务集成
- 地理编码 & 周边 POI

### Riki-1124 — 维修实现
- 租客报修申请
- 房东维修受理
- 维修进度跟踪
- 维修评价
- 维修工单管理

### renwc — 系统管理员角色设计
- RBAC 权限体系
- 管理员后台面板
- 用户管理（审核、封禁）
- 审计日志
- 安全策略（频率限制、Token 管理）

### JiaWu1211 — 支付流程完善
- 押金支付流程
- 租金支付流程
- 预约看房流程
- 电子合同签署
- 微信支付对接
- 退款处理

---

## 三、文件归属速查

| 文件/目录 | 负责人 |
|-----------|--------|
| `backend/app/services/property*.py` | lu-sir1219 |
| `frontend/src/views/Home.vue` | lu-sir1219 |
| `backend/app/services/notification*.py` | Michael9047 |
| `frontend/src/views/Notifications.vue` | Michael9047 |
| `backend/app/services/llm*.py` | shen25308 |
| `frontend/src/views/AiSearch.vue` | shen25308 |
| `backend/app/services/maintenance*.py` | Riki-1124 |
| `backend/app/api/v1/routes/admin.py` | renwc |
| `frontend/src/views/AdminWorkspace.vue` | renwc |
| `backend/app/services/payment*.py` | JiaWu1211 |
| `frontend/src/views/DepositPayment.vue` | JiaWu1211 |

> 完整归属见 `.github/CODEOWNERS`

---

## 四、协作约定

- 每人需在 GitHub 上添加对应的 CODEOWNERS 规则
- 修改他人负责的文件需提前沟通
- 共享基础设施（core/db/models 等）修改需至少 1 人 review
- commit 格式遵循 AGENTS.md 规范

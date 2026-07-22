# 消息通知系统 — 综合进度

> 最后更新：2026-07-21

---

## 架构概览

```
业务触发 → NotificationService.create_notification()
           ├── 写入 DB (notifications 表)
           └── _dispatch_channels()
                ├── Email  ──→ Celery Task ──→ EmailService (DirectMail > SMTP)
                ├── SMS    ──→ Celery Task ──→ SmsService (阿里云短信)    [未启用]
                └── WeChat ──→ Celery Task ──→ WeChatService (模板消息)   [部分启用]
```

---

## 发送通道

### 邮件（主力，已上线）

| 组件 | 文件 | 状态 |
|------|------|------|
| DirectMail 引擎 | `app/services/email_service.py` | ✅ 已配置 `rental.house@accomadation.xyz` |
| SMTP fallback | `app/services/email_service.py` | ✅ 自动降级 |
| 模板渲染 | `app/services/email_templates/` | ✅ 双层模板（base + 业务） |
| Celery 异步任务 | `app/tasks/notification_tasks.py` | ✅ `send_email_notification` + `send_email_notification_with_template` |
| 附件支持 | `app/services/email_service.py` | ✅ DirectMail 附件（合同 PDF） |

### 短信（代码就绪，未启用）

| 组件 | 文件 | 状态 |
|------|------|------|
| 阿里云短信 SDK | `app/services/sms_service.py` | ✅ 已封装 |
| Celery 任务 | `app/tasks/notification_tasks.py` | ⚠ `send_sms_notification` 代码完整但未接入通知流 |
| 通知流集成 | `app/services/notification_service.py` | ⚠ `_dispatch_channels` 中 SMS 分支存在但所有调用方传 `channels=["email"]` |

### 微信模板消息（部分启用）

| 组件 | 文件 | 状态 |
|------|------|------|
| 微信服务 | `app/services/wechat_service.py` | ✅ |
| 预约确认模板 | `app/tasks/notification_tasks.py` | ✅ 预约创建后发租客 |
| 预约提醒模板 | `app/tasks/notification_tasks.py` | ⚠ 模板代码完整，无定时任务实际触发 |
| 支付结果模板 | `app/tasks/payment_tasks.py` | ✅ 支付成功/失败后发租客 |
| 通知流集成 | `app/services/notification_service.py` | ❌ `_dispatch_channels` 中微信分支被注释 |

---

## 邮件模板清单

| 模板文件 | 场景 | 状态 |
|----------|------|------|
| `base.html` | 统一外壳（Header + Footer + 响应式） | ✅ |
| `welcome.html` | 用户注册欢迎 | ⚠ 模板已有但注册接口未调用（用通用 HTML） |
| `booking_confirm.html` | 预约确认（房源/时间/价格/地址） | ✅ |
| `contract_generated.html` | 合同生成通知 | ✅ |
| `contract_signed.html` | 合同签署完成 | ✅ |
| `password_reset.html` | 密码重置链接 | ✅ |
| `payment_created.html` | 支付已发起 | ✅ |
| `payment_received.html` | 支付到账 | ✅ |
| `payment_failed.html` | 支付失败 | ✅ |
| `payment_expired.html` | 支付过期 | ✅ |

---

## 通知类型 × 通道矩阵

| # | NotificationType | 触发时机 | 通知对象 | 邮件 | 短信 | 微信 |
|---|-----------------|----------|----------|------|------|------|
| 1 | `booking_created` | 租客创建预约 | 房东 | 📧 通用 | ❌ | ❌ |
| 2 | — | 租客创建预约 | 租客 | ❌ | ❌ | 💬 确认 |
| 3 | `booking_approved` | 房东通过 | 租客 | 📧 通用 | ❌ | ❌ |
| 4 | `booking_rejected` | 房东拒绝 | 租客 | 📧 通用 | ❌ | ❌ |
| 5 | `booking_cancelled` | 租客取消 | 房东 | 📧 通用 | ❌ | ❌ |
| 6 | `booking_completed` | 预约完成 | 租客+房东 | 📧 通用 | ❌ | ❌ |
| 7 | `payment_created` | 发起支付 | 租客+房东 | ✅ 模板（租客）/ 📧 通用（房东） | ❌ | ❌ |
| 8 | `payment_received` | 支付到账 | 租客+房东 | ✅ 模板（租客）/ 📧 通用（房东） | ❌ | 💬 租客 |
| 9 | `payment_failed` | 支付失败 | 租客 | ✅ 模板 | ❌ | 💬 租客 |
| 10 | `payment_expired` | 支付过期 | 租客 | ✅ 模板 | ❌ | ❌ |
| 11 | `contract_generated` | 合同生成 | 租客+房东 | 📧 通用 + PDF 附件 | ❌ | ❌ |
| 12 | `contract_signed` | 合同签署 | 租客+房东 | 📧 通用 + 已签 PDF | ❌ | ❌ |
| 13 | `auth_registration` | 注册成功 | 用户 | 📧 通用（welcome 模板未用） | ❌ | ❌ |
| 14 | `auth_password_reset` | 忘记密码 | 用户 | ✅ `password_reset` 模板 | ❌ | ❌ |
| 15 | `repair_*` | 报修相关 | — | ❌ | ❌ | ❌ |
| 16 | `system` | 系统通知 | — | ❌ | ❌ | ❌ |

---

## 数据库

| 表 | 文件 | 说明 |
|----|------|------|
| `notifications` | `app/models/notification.py` | 通知记录（user_id, type, title, content, is_read） |
| `NotificationType` 枚举 | `app/models/notification.py` | 19 种通知类型 |

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/notifications` | 获取当前用户通知列表 |
| GET | `/api/v1/notifications/unread-count` | 未读数量 |
| PATCH | `/api/v1/notifications/{id}/read` | 标记单条已读 |
| PATCH | `/api/v1/notifications/read-all` | 全部已读 |
| POST | `/api/v1/auth/forgot-password` | 发送密码重置邮件 |
| POST | `/api/v1/auth/reset-password` | 验证 token 并重置密码 |

### 前端页面

| 页面 | 文件 | 说明 |
|------|------|------|
| 通知中心 | `frontend/src/views/Notifications.vue` | 通知列表 + 已读/未读 + 全部已读 |
| 忘记密码 | `frontend/src/views/ForgotPassword.vue` | 输入邮箱 → 发送重置链接 |
| 重置密码 | `frontend/src/views/ResetPassword.vue` | URL token → 设新密码 |
| 登录页入口 | `frontend/src/views/Login.vue` | "忘记密码？"链接 |

---

## 已知缺口

### 高优先级
- [ ] **短信通道接入通知流** — 关键节点（通过/拒绝、支付到账、合同签署）应走短信
- [ ] **房东侧支付通知补充专属模板** — 当前用通用 HTML
- [ ] **预约状态变更补充专属模板** — booking_approved/rejected/cancelled/completed 用通用 HTML
- [ ] **合同通知补充专属模板** — contract_generated/signed 用通用 HTML

### 中优先级
- [ ] **注册欢迎邮件改用 welcome 模板** — 模板已有，注册接口未调用
- [ ] **看房提醒定时任务打通** — `send_booking_reminder_message` 存在但无 cron 触发
- [ ] **租客创建预约后发邮件确认** — 当前只发微信模板消息

### 低优先级
- [ ] **用户通知偏好设置** — 让用户选择邮件/短信/微信通道
- [ ] **报修通知** — repair_created/assigned/completed/status_change 均未接入
- [ ] **系统通知** — system 类型从未使用
- [ ] **微信模板消息全量接入通知流** — `_dispatch_channels` 中微信分支仍被注释

---

## 配置项

```bash
# 阿里云 DirectMail（主引擎）
DM_ACCESS_KEY_ID=xxx
DM_ACCESS_KEY_SECRET=xxx
DM_ACCOUNT_NAME=rental.house@accomadation.xyz
DM_FROM_ALIAS=Rental Housing
DM_REGION_ID=cn-hangzhou
DM_ENDPOINT=dm.aliyuncs.com

# SMTP（fallback）
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=3158309731@qq.com
SMTP_PASSWORD=xxx
SMTP_FROM_EMAIL=3158309731@qq.com
SMTP_FROM_NAME=Rental Housing
SMTP_USE_TLS=true

# 阿里云短信（SMS，已配置未接入通知流）
SMS_ACCESS_KEY_ID=xxx
SMS_SIGN_NAME=xxx
SMS_TEMPLATE_CODE=SMS_001
```

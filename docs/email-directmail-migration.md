# 邮件服务迁移：QQ SMTP → 阿里云 DirectMail

> 日期：2026-07-19
> 作者：Claude Code + Michael

---

## 背景

原有邮件通知使用 QQ 邮箱 SMTP 直连，仅支持纯 HTML 正文，无附件能力。业务需求扩展后需要：

- 合同生成后发送 PDF 附件
- 合同签署后发送签署确认邮件（含签署版合同）
- 品牌化的预约确认邮件

---

## 技术方案

### 发送通道

```
DirectMail SDK（主）→ SMTP（fallback）→ skip（兜底）
```

| 引擎 | 优先级 | 附件 | 模板 | 使用场景 |
|------|--------|------|------|---------|
| 阿里云 DirectMail | 主 | ✅ | ✅ | 日常 |
| QQ 邮箱 SMTP | fallback | ❌ | ❌ | DirectMail 不可用时的紧急降级 |

### 依赖

```
alibabacloud_dm20151123>=1.0.0    # DirectMail API
alibabacloud_tea_openapi>=0.3.0   # 阿里云 OpenAPI 基础设施
alibabacloud_tea_util>=0.3.0      # 阿里云工具
weasyprint>=62.0                  # 合同 PDF 生成
```

### 配置项

| 环境变量 | 值 | 说明 |
|----------|-----|------|
| `DM_ACCESS_KEY_ID` | 同 SMS AK | 复用 SMS 的 AccessKey |
| `DM_ACCESS_KEY_SECRET` | 同 SMS SK | |
| `DM_ACCOUNT_NAME` | `noreply@accomadation.xyz` | 发件地址 |
| `DM_FROM_ALIAS` | `Rental Housing` | 发件人显示名 |
| `DM_REGION_ID` | `cn-hangzhou` | |
| `DM_ENDPOINT` | `dm.aliyuncs.com` | |

### 邮件模板

HTML 模板位于 `backend/app/services/email_templates/`：

| 模板 | 触发场景 |
|------|---------|
| `welcome.html` | 注册成功 |
| `booking_confirm.html` | 预约创建 |
| `contract_generated.html` | 合同生成（含 PDF 附件） |
| `contract_signed.html` | 合同签署（含签署版 PDF 附件） |

模板使用 Python `str.format()` 填充变量，双层架构：

```
base.html（完整 HTML + CSS）
  └── 各业务模板（只有 body 内容）
```

### 合同 PDF 生成

`ContractPdfService` → weasyprint 将合同纯文本渲染为 HTML → PDF。

---

## 阿里云控制台操作（需人工完成）

### 域名

- **域名**：`accomadation.xyz`
- **注册商**：阿里云万网
- **状态**：已购买，实名认证中

### 待完成步骤

1. 实名认证通过
2. DirectMail 控制台 → 发信域名 → 添加 `accomadation.xyz`（同账号免 DNS 验证）
3. 发信地址 → 新建 `noreply@accomadation.xyz`
4. 收验证邮件确认发信地址
5. 端到端测试：注册 → 预约 → 合同生成 → 检查邮件投递

---

## 改动文件

| 文件 | 改动 |
|------|------|
| `backend/app/core/config.py` | 新增 7 个 DM_* 配置项 |
| `backend/app/services/email_service.py` | 重写：DirectMail + SMTP fallback + Attachment 类型 |
| `backend/app/services/email_templates/` | 新增：5 个 HTML 邮件模板 + render 函数 |
| `backend/app/services/contract_pdf_service.py` | 新增：weasyprint HTML→PDF |
| `backend/app/services/contract_service.py` | 合同生成/签署时生成 PDF 附件 |
| `backend/app/services/notification_service.py` | `email_attachments` 参数 |
| `backend/app/tasks/notification_tasks.py` | 附件 Base64 解码 + 转发 |
| `backend/requirements.txt` | 新增 4 个依赖 |

---

## 注意事项

- DirectMail 单封邮件总大小 ≤15MB，PDF 建议控制在 5MB 以内
- 每天免费 200 封，超出按量付费 ¥2/1000 封
- weasyprint 需要系统中文字体（部署时安装 `fonts-noto-cjk`）
- 旧 SMTP 配置保留，DirectMail 稳定后移除

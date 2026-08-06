# Dropbox Sign 嵌入式签署接入说明

## 签署流程

1. 管理员创建一个平台默认模板绑定，或为特定公寓创建覆盖绑定。
2. 租客完成个人资料并确认电子签署条款后，请求嵌入式签署会话。
3. 服务端按“公寓模板优先、平台默认模板兜底”选择模板，将已保存的个人资料映射为 Dropbox Sign 自定义字段。
4. 服务端返回短时 `sign_url`；前端仅用它初始化 Dropbox Sign 的嵌入组件。
5. Dropbox Sign 回调 `signature_request_all_signed` 后，系统记录审计事件并将合同标记为 `signed`。

签署不需要人工审核；但必须在签署前记录租客的电子签署同意和条款版本。

## 模板字段映射

`field_mapping` 的键是 Dropbox Sign 模板里的自定义字段名，值只能使用下列受控来源：

| 映射来源 | 含义 |
| --- | --- |
| `tenant.chinese_name` | 租客中文姓名 |
| `tenant.given_name` | 拼音名 |
| `tenant.surname` | 拼音姓 |
| `tenant.email` | 签署邮箱 |
| `tenant.phone` | 租客电话 |
| `tenant.birth_date` | 出生日期 |
| `booking.contract_start` | 合同开始日期 |
| `booking.contract_end` | 合同结束日期 |
| `booking.room_number` | 房间号 |
| `contract.agreement_number` | 合同编号 |

示例：`{"tenant_full_name":"tenant.chinese_name","lease_start":"booking.contract_start"}`。

## 上线配置

仅在后端本地 `.env` 设置，绝不能放入前端、Git 或 URL：

```dotenv
DROPBOX_SIGN_API_KEY=
DROPBOX_SIGN_CLIENT_ID=
DROPBOX_SIGN_WEBHOOK_ENABLED=true
DROPBOX_SIGN_TEST_MODE=false
```

`DROPBOX_SIGN_TEST_MODE=false` 才会创建生产签署请求。上线前需要在 Dropbox Sign 后台配置嵌入式 `client_id`、回调 URL 以及模板签署角色；模板、签署主体和适用法域是否满足法律效力仍应由业务方的法务确认。

## 回调

回调地址为 `POST /api/v1/contracts/dropbox-sign/webhook`。服务端使用 `event_time + event_type` 与 API Key 的 HMAC-SHA256 校验 `event_hash`，并按事件摘要幂等保存。接口仅返回 Dropbox Sign 要求的固定确认文本。

## 首批上线基线

- 首批适用地区为英国和新加坡，合同使用双语文本。
- 当前只支持租客单方签署；若某个公寓或法域要求房东、见证人或额外签署人，必须先扩展多签署人流程，不能复用单签流程上线。
- 身份核验策略在法务确认前保持可配置，不将平台登录、邮箱或模拟签署表述为 KYC 或法定身份认证。
- 已签署合同、模板绑定快照、供应商请求标识和回调审计材料建议至少留存 7 年；留存期内租客和有管理权限的 BM 可下载，管理员可审计。实际留存期以适用法律、税务和法务意见为准。
- 租客可重新进入同一签署请求；系统优先重新取得短时 `sign_url`，不重复创建有效签署请求。

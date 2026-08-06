# 微信扫码登录 — 技术文档

> 实施日期：2026-08-06

## 概述

Web 端新增微信开放平台扫码登录（OAuth 2.0），替代 Login.vue 中原有的占位按钮。用户点击"微信登录"→ 弹出二维码 → 微信扫码授权 → 自动创建/绑定账号 → 登录进系统。

## 架构

```
用户点击微信登录
    ↓
前端 GET /auth/wechat/qr-url → 获取 qr_url + state
    ↓
前端渲染二维码 (qrcode lib) + 轮询 GET /auth/wechat/qr-status/{state}
    ↓
用户扫码 → 微信重定向 → GET /auth/wechat/callback?code=&state=
    ↓
后端存 code 到 Redis → 前端轮询拿到 code → POST /auth/wechat/qr-login
    ↓
后端 exchange_qr_code(code) → openid → 查找/创建 User → 返回 JWT
    ↓
前端收到 token → 登录成功 → 跳转首页
```

## 与小程序登录的区别

| | 小程序登录 | 扫码登录 (新增) |
|---|---|---|
| API | `jscode2session` | `oauth2/access_token` |
| 适用场景 | 微信内 `wx.login()` | Web 页面扫码 / 微信内 H5 授权 |
| 凭证 | `WECHAT_APPID` + `WECHAT_SECRET` | `WECHAT_OPEN_APPID` + `WECHAT_OPEN_SECRET` |
| 回调 | 无（纯后端交换） | 有（微信重定向到 callback URL） |

两套凭证独立，但复用同一个 `User.wechat_openid` 字段存储身份。若小程序和网站应用绑定到同一开放平台账号，可通过 `unionid` 实现跨平台用户识别。

## 涉及文件

### 后端
| 文件 | 变更 |
|------|------|
| `backend/app/core/config.py` | +4 配置项（open_appid, open_secret, redirect_uri, dev_mode）|
| `backend/app/core/security.py` | +4 Redis 函数（state 存储/校验, code 暂存/消费）|
| `backend/app/services/wechat_service.py` | +2 方法（get_qr_connect_url, exchange_qr_code），+1 数据类 |
| `backend/app/services/auth_service.py` | +1 方法（wechat_qr_login）|
| `backend/app/schemas/auth.py` | +3 Schema（QrUrlResponse, QrLoginRequest, QrStatusResponse）|
| `backend/app/api/v1/routes/wechat.py` | +4 端点（qr-url, qr-login, qr-status, callback）|

### 前端
| 文件 | 变更 |
|------|------|
| `frontend/src/types/auth.ts` | +3 类型 |
| `frontend/src/services/auth.ts` | +3 API 方法 |
| `frontend/src/stores/auth.ts` | +1 action（wechatQrLogin）|
| `frontend/src/views/Login.vue` | 替换占位按钮 → 二维码弹窗 + 轮询 |
| `frontend/src/views/WeChatCallback.vue` | **新建** — OAuth 回调处理页 |
| `frontend/src/router/index.ts` | +1 路由（/auth/wechat/callback）|

## 环境变量

```bash
# 微信开放平台（Web 扫码登录）
WECHAT_OPEN_APPID=           # 开放平台网站应用 AppID
WECHAT_OPEN_SECRET=          # 开放平台网站应用 AppSecret
WECHAT_OPEN_REDIRECT_URI=    # OAuth 回调地址（如 https://your-domain.com/api/v1/auth/wechat/callback）
WECHAT_OPEN_DEV_MODE=true    # 开发模式：跳过真实微信 API，用 mock openid
```

## 开发模式

`WECHAT_OPEN_DEV_MODE=true`（默认）时：
- `/auth/wechat/qr-url` — 生成的 QR URL 中 appid 为空（二维码不可扫，但 state 有效）
- `/auth/wechat/qr-callback` — 用 `code` 的 MD5 hash 生成确定性 mock openid
- `/auth/wechat/qr-login` — 接受 mock code+state 完成登录

测试方式：访问 `http://localhost:5173/login`，点击微信登录，然后手动访问：
```
http://localhost:5173/auth/wechat/callback?code=test&state=<从 Redis 获取的有效 state>
```

## 甲方待办

1. 前往 [open.weixin.qq.com](https://open.weixin.qq.com) 注册开发者账号（需企业资质）
2. 创建**网站应用**，获取 AppID + AppSecret
3. 在应用设置中配置 OAuth 回调域名
4. 将凭证填入 `.env`，设 `WECHAT_OPEN_DEV_MODE=false`

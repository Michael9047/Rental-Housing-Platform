# 第三方服务注册配置指南

> 面向甲方交付 — 本文档列出系统运行所需的全部第三方服务账号注册与 API Key 获取流程。
>
> 更新日期：2026-08-06

---

## 目录

1. [总览](#总览)
2. [LLM 大语言模型](#1-llm-大语言模型)
   - [1.1 DeepSeek（主引擎）](#11-deepseek主引擎)
   - [1.2 OpenAI（备用引擎）](#12-openai备用引擎)
3. [Embedding 向量化模型](#2-embedding-向量化模型)
   - [2.1 智谱 AI（主引擎）](#21-智谱-ai主引擎)
   - [2.2 OpenAI Embedding（备用引擎）](#22-openai-embedding备用引擎)
4. [Google Maps 地图服务](#3-google-maps-地图服务)
5. [高德地图（中国大陆）](#4-高德地图中国大陆)
6. [短信服务（阿里云）](#5-短信服务阿里云)
7. [邮件服务（阿里云 DirectMail）](#6-邮件服务阿里云-directmail)
8. [微信开放平台（Web 扫码登录）](#7-微信开放平台web-扫码登录)
9. [OpenRouteService（OSM 全球路线）](#8-openrouteserviceosm-全球路线)
10. [环境变量汇总](#9-环境变量汇总)

---

## 总览

| 服务 | 用途 | 是否必需 | 费用模式 |
|------|------|----------|----------|
| DeepSeek | AI 搜房 — 自然语言解析 + 房源摘要 | **必需** | 按量付费，极低 |
| 智谱 AI | 房源向量化 (Embedding) — 语义搜索 | **必需** | 按量付费 |
| OpenAI | LLM + Embedding 备用引擎 | 建议配置（备用） | 按量付费 |
| Google Maps | 海外地图 — 地理编码 / POI / 路线 | **必需**（海外场景） | 按量付费，$200/月免费额度 |
| 高德地图 | 中国大陆地图 — 地理编码 / POI / 路线 | **必需**（国内场景） | 免费额度 + 按量付费 |
| 阿里云短信 | 验证码 + 业务通知 | **必需** | 按条计费 |
| 阿里云 DirectMail | 邮件发送（合同、通知等） | **必需** | 按量付费（免费额度 200 封/天） |
| 微信开放平台 | Web 端扫码登录 | **必需** | 认证费 ¥300/年 |
| OpenRouteService | OSM 全球路线规划（Google 备用） | 建议配置 | 免费额度 |

---

## 1. LLM 大语言模型

系统使用 LLM 实现 AI 智能搜房：将用户的自然语言描述（如"苏州园区 2000-4000 的两居室"）解析为结构化搜索参数，并生成友好的房源推荐摘要。

### 1.1 DeepSeek（主引擎）

> 默认 LLM 引擎，成本极低（约 OpenAI 的 1/10），中文能力强。

**注册流程：**

1. 访问 [platform.deepseek.com](https://platform.deepseek.com)
2. 点击右上角"注册"，使用手机号或邮箱注册账号
3. 登录后进入 [API Keys 页面](https://platform.deepseek.com/api_keys)
4. 点击"创建 API Key"，输入名称（如 `rental-platform`）
5. **立即复制保存** — Key 仅显示一次

**充值：**
- 进入"充值"页面，按预估用量充值（建议首次充值 ¥50-100）
- 定价参考：deepseek-chat 模型 ¥1/M tokens（输入），¥2/M tokens（输出）

**填入配置：**

```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_CHAT_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 1.2 OpenAI（备用引擎）

> DeepSeek 不可用时自动降级到 OpenAI，建议配置以提高可用性。

**注册流程：**

1. 访问 [platform.openai.com](https://platform.openai.com)
2. 注册 OpenAI 账号（需海外手机号验证，可用虚拟号码平台）
3. 登录后进入 [API Keys 页面](https://platform.openai.com/api-keys)
4. 点击 "Create new secret key"，输入名称
5. **立即复制保存**

**充值：**
- 进入 Billing 页面绑定信用卡或预付充值
- 定价参考：gpt-4o 约 $2.50/$10.00 per 1M tokens（输入/输出）

**填入配置：**

```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_BASE_URL=  # 留空使用默认，或填写代理地址
```

---

## 2. Embedding 向量化模型

系统使用 Embedding 将房源信息（标题、描述、地址等）转换为 1536 维向量存储于 pgvector，支撑语义相似度搜索。用户搜"近地铁带阳台的公寓"时，即使房源描述里写的是"步行 3 分钟到 MRT，有独立露台"，也能被语义匹配到。

### 2.1 智谱 AI（主引擎）

> 默认 Embedding 引擎，中文语义效果好，支持自定义输出维度（1536），价格远低于 OpenAI。

**注册流程：**

1. 访问 [open.bigmodel.cn](https://open.bigmodel.cn)
2. 点击"注册"，使用手机号注册（需实名认证）
3. 登录后进入 [API Keys 页面](https://open.bigmodel.cn/usercenter/apikeys)
4. 点击"创建 API Key"，输入名称
5. **立即复制保存**

**充值：**
- 进入"资源管理"→"充值"，建议首次充值 ¥20-50
- 定价参考：embedding-3 模型 ¥0.0005 / 1K tokens

**填入配置：**

```bash
ZHIPU_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.xxxxxxxx
ZHIPU_EMBEDDING_MODEL=embedding-3
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
EMBEDDING_DIMENSIONS=1536
```

### 2.2 OpenAI Embedding（备用引擎）

> 智谱不可用时自动降级。与上方 OpenAI API Key 共用同一把 Key。

**配置要求：**
- 如果已配置 `OPENAI_API_KEY`，则自动可用，无需额外注册
- 默认模型 `text-embedding-3-small`，$0.02/1M tokens

```bash
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

---

## 3. Google Maps 地图服务

> 海外房源的地图展示、周边 POI 检索、通勤时间计算全部依赖 Google Maps。
> 所有 API 使用**同一把 API Key**。

### 3.1 注册 Google Cloud 账号

1. 访问 [cloud.google.com](https://cloud.google.com)
2. 点击"Get started for free"，使用 Google 账号登录
3. 首次注册可获 $300 免费试用额度（90 天有效）
4. 填写基本信息（国家、信用卡）完成注册
5. 进入 [Google Cloud Console](https://console.cloud.google.com)

### 3.2 创建项目

1. 顶部项目下拉菜单 → 点击"新建项目"
2. 项目名称：`rental-platform`（或自定义）
3. 点击"创建"
4. 等待创建完成，切换到新项目

### 3.3 启用必需的 API

进入 [API 库](https://console.cloud.google.com/apis/library)，依次搜索并**启用**以下 5 个 API：

| API 名称 | 用途 | 启用链接 |
|----------|------|----------|
| Geocoding API | 地址 → 经纬度转换 | [启用](https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com) |
| Places API (New) | 周边设施 POI 检索 | [启用](https://console.cloud.google.com/apis/library/places.googleapis.com) |
| Distance Matrix API | 批量通勤时间计算 | [启用](https://console.cloud.google.com/apis/library/distance-matrix-backend.googleapis.com) |
| Directions API | 路线规划 + polyline | [启用](https://console.cloud.google.com/apis/library/directions-backend.googleapis.com) |
| Maps JavaScript API | 前端地图展示 | [启用](https://console.cloud.google.com/apis/library/maps-javascript-backend.googleapis.com) |

> 点击每个链接 → 点击"启用"。如果提示需要结算账号，请先完成 3.4 步。

### 3.4 绑定结算账号

> Google Maps 即使有 $200/月免费额度，也必须绑定结算账号才能使用。

1. 左侧菜单 → [结算](https://console.cloud.google.com/billing)
2. 如果还没有结算账号，点击"添加结算账号"
3. 选择"Google Cloud 结算账号"，填写信用卡信息
4. 将结算账号关联到你的项目：
   - 结算页面 → "我的项目" → 找到 `rental-platform` → 点击 ⋮ → "更改结算账号"

### 3.5 创建 API Key

1. 左侧菜单 → [API 和服务 → 凭据](https://console.cloud.google.com/apis/credentials)
2. 点击顶部"创建凭据"→"API 密钥"
3. Key 创建后**立即复制保存**

### 3.6 限制 API Key（安全建议）

> **强烈建议**为 API Key 设置限制，防止被盗用造成经济损失。

1. 在凭据页面，点击刚创建的 Key 名称进入编辑
2. **API 限制**：选择"限制密钥"→ 下拉勾选上述 5 个 API
3. **应用限制**：
   - 后端 Key（`.env` 中 `GM_API_KEY`）：选择"无"或"IP 地址"（填服务器 IP）
   - 前端 Key（`.env` 中 `VITE_GM_KEY`）：选择"HTTP 来源"→ 填写你的网站域名
   - 建议后端和前端使用**不同的 Key**
4. 点击"保存"

### 3.7 设置预算告警

> 防止意外超支。

1. 左侧菜单 → [结算 → 预算和提醒](https://console.cloud.google.com/billing/budgets)
2. 点击"创建预算"
3. 预算类型：指定金额 → $50/月（或按需设置）
4. 勾选"触发提醒"→ 设置 50%、90%、100% 三个阈值
5. 输入告警接收邮箱

### 3.8 免费额度说明

Google Maps 每月提供 **$200 免费额度**，对应大致用量：

| API | 免费调用次数/月 |
|-----|----------------|
| Geocoding | ~40,000 次 |
| Places (New) | ~5,000 次（Text Search）/ 5,000 次（Nearby） |
| Distance Matrix | ~40,000 个元素 |
| Directions | ~40,000 次 |
| Maps JavaScript | 无限（需 API Key，按加载次数计费很低） |

超出后按实际用量计费。一般规模的租房平台**月费在免费额度以内**。

### 3.9 填入配置

**后端 `.env`：**

```bash
GM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**前端 `.env`：**

```bash
VITE_GM_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

---

## 4. 高德地图（中国大陆）

> 国内房源的地理编码、周边 POI、通勤路线由高德地图提供。与 Google Maps 互补，系统根据房源所属区域自动选择引擎。

### 4.1 注册高德开放平台

1. 访问 [lbs.amap.com](https://lbs.amap.com)
2. 右上角"注册"，使用手机号注册
3. 进入[控制台](https://console.amap.com/dev/index)

### 4.2 创建应用

1. 控制台 → "应用管理"→"我的应用"→"创建应用"
2. 应用名称：`租房平台`
3. 应用类型：选择"Web 服务"

### 4.3 创建 Key

需要创建 **两把 Key**：

| Key 类型 | 服务平台 | 用途 | 对应配置 |
|----------|----------|------|----------|
| Web 服务 | Web 服务 | 后端 API 调用（地理编码/POI/路线） | `AMAP_WEB_KEY` |
| Web 端(JS API) | Web 端 | 前端地图展示 | `AMAP_JS_KEY` / `VITE_AMAP_KEY` |

1. 在应用详情页点击"添加 Key"
2. **Web 服务 Key**：服务平台选择"Web 服务"，IP 白名单填服务器 IP
3. **JS API Key**：服务平台选择"Web 端(JS API)"，域名白名单填你的网站域名
4. 分别保存两把 Key

### 4.4 填入配置

**后端 `.env`：**

```bash
AMAP_WEB_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**前端 `.env`：**

```bash
VITE_AMAP_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> 前端也可以复用后端的 Web 服务 Key 填入 `AMAP_JS_KEY` 配置项（效果同 `VITE_AMAP_KEY`）。

### 4.5 免费额度说明

高德地图对大部分 API 提供**免费配额**：

| API | 免费调用次数/日 |
|-----|----------------|
| 地理编码 | 6,000 次 |
| 周边搜索 | 5,000 次 |
| 路线规划 | 5,000 次 |

超出后可按需购买配额包。

---

## 5. 短信服务（阿里云）

> 短信分为两类：
> - **验证码短信** — 阿里云号码认证服务（dypnsapi），用于手机号登录/注册
> - **通知短信** — 阿里云短信服务（dysmsapi），用于预约确认、支付提醒等

### 5.1 注册阿里云账号

1. 访问 [aliyun.com](https://www.aliyun.com)
2. 右上角"注册"，用手机号注册
3. 完成实名认证（企业认证需营业执照）

### 5.2 开通短信服务

1. 进入[短信服务控制台](https://dysms.console.aliyun.com)
2. 如果未开通，点击"立即开通"

### 5.3 创建 AccessKey

1. 鼠标悬停右上角头像 → [AccessKey 管理](https://ram.console.aliyun.com/manage/ak)
2. 点击"创建 AccessKey"
3. 选择"继续使用 AccessKey"（或选择使用 RAM 子账号，更安全）
4. 手机验证 → 创建成功
5. **立即复制保存 AccessKey ID 和 AccessKey Secret**

> ⚠ 如果使用同一套 AccessKey 同时用于验证码和通知短信，只需创建一次。如果希望权限隔离，可为验证码和通知分别创建 RAM 子账号。

### 5.4 验证码短信配置

#### 5.4.1 申请签名

1. [短信服务控制台](https://dysms.console.aliyun.com) → "国内消息"→"签名管理"→"添加签名"
2. 签名类型：选择"网站"或"App"
3. 签名名称：如"XX租房"（显示在短信开头：【XX租房】）
4. 上传证明材料（网站备案截图等）
5. 提交审核，约 1-2 个工作日

#### 5.4.2 申请模板

1. "模板管理"→"添加模板"
2. 模板类型：验证码
3. 模板内容：`您的验证码是${code}，有效期${min}分钟，请勿泄露。`
4. 提交审核

#### 5.4.3 填入配置

```bash
SMS_PROVIDER=aliyun
SMS_ACCESS_KEY_ID=LTAI5tXXXXXXXXXXXXXXXXXX
SMS_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SMS_SIGN_NAME=XX租房
SMS_TEMPLATE_CODE=SMS_XXXXXXXXX
SMS_SCHEME_NAME=default
SMS_ENDPOINT=dypnsapi.aliyuncs.com
```

### 5.5 通知短信配置

通知短信可为每种业务场景申请不同模板（预约确认、支付成功、合同到期等）。

#### 5.5.1 申请模板

为每种通知类型分别申请模板：

| 通知类型 | 模板内容示例 |
|----------|-------------|
| booking_created | `您好${name}，您的看房预约已提交，${title}，时间${time}，请保持电话畅通。` |
| booking_confirmed | `您好${name}，您的看房预约已确认，${title}，${time}，地址${address}。` |
| payment_received | `${name}您好，已收到您的${amount}元付款，${item}，感谢您的信任。` |
| contract_signed | `${name}您好，${title}的合同已签署生效，合同号${contract_no}。` |

#### 5.5.2 填入配置

> 模板映射为 JSON 字符串，key 是通知类型，value 是阿里云模板 CODE。

```bash
SMS_NOTIFY_ACCESS_KEY_ID=LTAI5tXXXXXXXXXXXXXXXXXX
SMS_NOTIFY_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SMS_NOTIFY_SIGN_NAME=XX租房
SMS_NOTIFY_TEMPLATE_MAP={"booking_created":"SMS_XXX","booking_confirmed":"SMS_YYY","payment_received":"SMS_ZZZ"}
```

### 5.6 费用说明

- 验证码短信：¥0.045/条（国内）
- 通知短信：¥0.045/条（国内）
- 建议首次充值 ¥500-1000

> 📸 **短信已配置完成，此处可直接贴截图。**

---

## 6. 邮件服务（阿里云 DirectMail）

> 系统使用阿里云 DirectMail 发送邮件，支持 HTML 正文 + 附件（合同 PDF 等）。
> DirectMail 不可用时自动降级到 SMTP 通道。

### 6.1 DirectMail 配置（推荐）

DirectMail 是阿里云的企业邮件发送服务，送达率高，支持附件。

#### 6.1.1 开通 DirectMail

1. 访问 [DirectMail 控制台](https://dm.console.aliyun.com)
2. 如果未开通，点击"立即开通"
3. 选择按量付费模式

#### 6.1.2 验证发件域名

> DirectMail 要求验证发件域名所有权，不能使用公共邮箱地址（如 @gmail.com）。

1. DirectMail 控制台 → "发信域名"→"新建域名"
2. 输入你的域名（如 `notice.your-rental-platform.com`）
3. 按提示在域名 DNS 中添加 TXT 记录和 MX 记录
4. 等待 DNS 生效后点击"验证"
5. 域名状态变为"验证通过"

#### 6.1.3 设置发件地址

1. "发信地址"→"新建发信地址"
2. 选择已验证的发信域名
3. 输入账号（如 `noreply`，则发件地址为 `noreply@notice.your-rental-platform.com`）
4. 设置回信地址
5. 设置发信昵称（如"XX租房"）
6. 创建完成

#### 6.1.4 获取 AccessKey

如果还没有 AccessKey，参考 [5.3 节](#53-创建-accesskey) 创建。DirectMail 可复用短信同一套 AccessKey。

#### 6.1.5 填入配置

```bash
# ── DirectMail（主引擎） ──
DM_ACCESS_KEY_ID=LTAI5tXXXXXXXXXXXXXXXXXX
DM_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DM_ACCOUNT_NAME=noreply@notice.your-rental-platform.com
DM_FROM_ALIAS=XX租房
DM_REGION_ID=cn-hangzhou
DM_ENDPOINT=dm.aliyuncs.com
DM_TIMEOUT_SECONDS=10.0
```

### 6.2 SMTP 配置（备用/开发环境）

> 生产环境建议 DirectMail。SMTP 可作为开发和测试用。

以 QQ 邮箱为例：

1. 登录 QQ 邮箱 → 设置 → 账户
2. 开启"POP3/SMTP 服务"
3. 按提示发送短信获取授权码
4. 记录 16 位授权码

```bash
# ── SMTP（备用通道） ──
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=xxxxxxxxxx@qq.com
SMTP_PASSWORD=xxxxxxxxxxxxxxxx    # 授权码，不是QQ密码
SMTP_FROM_NAME=XX租房
SMTP_FROM_EMAIL=xxxxxxxxxx@qq.com
SMTP_USE_TLS=true
SUPPORT_EMAIL=xxxxxxxxxx@qq.com
```

### 6.3 费用说明

| 模式 | 免费额度 | 超出后 |
|------|----------|--------|
| DirectMail 按量付费 | 200 封/天 | ¥0.01/封（1000 封以内） |
| SMTP（QQ 邮箱） | 500 封/天 | — |

---

## 7. 微信开放平台（Web 扫码登录）

> 用户在 Web 端点击"微信登录"→ 弹出二维码 → 微信扫码授权 → 自动登录。
> 此功能需要微信开放平台**网站应用**，与小程序是两套独立凭证。

### 7.1 注册微信开放平台

1. 访问 [open.weixin.qq.com](https://open.weixin.qq.com)
2. 点击"注册"，选择"开放平台"
3. 填写邮箱、密码等信息
4. 邮箱激活 → 完善开发者资料

### 7.2 开发者资质认证

> ⚠ **必须完成开发者资质认证才能创建网站应用。**

1. 登录开放平台 → "账号中心"→"开发者资质认证"
2. 企业用户：上传营业执照、法人身份证、对公账户信息等
3. 支付认证费用：**¥300/年**
4. 等待审核（约 1-3 个工作日）

### 7.3 创建网站应用

1. 开放平台 → "管理中心"→"网站应用"→"创建网站应用"
2. 填写应用信息：
   - 应用名称：如"XX租房"
   - 应用简介：一句话说明用途
   - 应用官网：你的网站域名
   - 应用图标：上传 logo（108×108 px）
3. 填写**授权回调域**：
   - 输入你的网站域名（不带 `https://`），如 `your-domain.com`
   - ⚠ 回调地址为 `https://your-domain.com/api/v1/auth/wechat/callback`，只需填域名部分
4. 提交审核（约 1-3 个工作日）

### 7.4 获取凭证

1. 审核通过后，进入应用详情
2. 查看 AppID 和 AppSecret
3. **AppSecret 需要管理员扫码才能查看**

### 7.5 填入配置

```bash
# ── 微信开放平台 OAuth（Web 扫码登录）──
WECHAT_OPEN_APPID=wxXXXXXXXXXXXXXXXX
WECHAT_OPEN_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_OPEN_REDIRECT_URI=https://your-domain.com/api/v1/auth/wechat/callback
WECHAT_OPEN_DEV_MODE=false    # 生产环境必须设为 false
```

### 7.6 上线前检查清单

- [ ] 服务器已部署 HTTPS（微信 OAuth 要求回调地址为 HTTPS）
- [ ] 回调地址在微信开放平台已配置（域名必须一致）
- [ ] `WECHAT_OPEN_DEV_MODE=false`
- [ ] 前端 `VITE_API_BASE_URL` 已指向生产域名

---

## 8. OpenRouteService（OSM 全球路线）

> Google Maps 不可用时的降级方案，基于 OpenStreetMap 数据，免费额度充足。

### 8.1 注册

1. 访问 [openrouteservice.org](https://openrouteservice.org)
2. 右上角"Sign Up"，使用邮箱注册
3. 登录后进入 [Dashboard](https://openrouteservice.org/dev/#/home)
4. 点击"Request a token"
5. 输入 Token 名称（如 `rental-platform`）
6. 复制生成的 API Key

### 8.2 填入配置

```bash
ORS_API_KEY=5b3ce3597851110001cf6248xxxxxxxxxxxxxxxxxxxxxxxx
ORS_DIRECTIONS_URL=https://api.openrouteservice.org/v2/directions
ORS_TIMEOUT_SECONDS=8.0
```

### 8.3 免费额度

| 模式 | 免费调用量 |
|------|-----------|
| 免费 Token | 2,000 次/天 |
| 注册用户 | 40,000 次/天 |

---

## 9. 环境变量汇总

以下为生产环境 `.env` 完整模板，按上方流程逐一填写。

> ⚠ 标记 `[可选]` 的为非必需项，但建议尽量配置以提高可用性。

```bash
# ═══════════════════════════════════════════════════════════
# LLM — AI 搜房（DeepSeek 主引擎 + OpenAI 备用）
# ═══════════════════════════════════════════════════════════
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_CHAT_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com

# [可选] OpenAI 备用引擎
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# ═══════════════════════════════════════════════════════════
# Embedding — 房源向量化（智谱主引擎 + OpenAI 备用）
# ═══════════════════════════════════════════════════════════
ZHIPU_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.xxxxxxxx
ZHIPU_EMBEDDING_MODEL=embedding-3
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
EMBEDDING_DIMENSIONS=1536

# ═══════════════════════════════════════════════════════════
# 地图服务
# ═══════════════════════════════════════════════════════════
# Google Maps（海外）
GM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# 高德地图（中国大陆）
AMAP_WEB_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AMAP_JS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# [可选] OpenRouteService（Google 备用）
ORS_API_KEY=5b3ce3597851110001cf6248xxxxxxxxxxxxxxxxxxxxxxxx

# ═══════════════════════════════════════════════════════════
# 短信（阿里云）
# ═══════════════════════════════════════════════════════════
SMS_PROVIDER=aliyun
SMS_ACCESS_KEY_ID=LTAI5tXXXXXXXXXXXXXXXXXX
SMS_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SMS_SIGN_NAME=XX租房
SMS_TEMPLATE_CODE=SMS_XXXXXXXXX
SMS_SCHEME_NAME=default
SMS_ENDPOINT=dypnsapi.aliyuncs.com

# [可选] 通知短信
SMS_NOTIFY_ACCESS_KEY_ID=LTAI5tXXXXXXXXXXXXXXXXXX
SMS_NOTIFY_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SMS_NOTIFY_SIGN_NAME=XX租房
SMS_NOTIFY_TEMPLATE_MAP={"booking_created":"SMS_XXX","payment_received":"SMS_YYY"}

# ═══════════════════════════════════════════════════════════
# 邮件（阿里云 DirectMail + SMTP 备用）
# ═══════════════════════════════════════════════════════════
# DirectMail（主引擎）
DM_ACCESS_KEY_ID=LTAI5tXXXXXXXXXXXXXXXXXX
DM_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DM_ACCOUNT_NAME=noreply@notice.your-domain.com
DM_FROM_ALIAS=XX租房
DM_REGION_ID=cn-hangzhou
DM_ENDPOINT=dm.aliyuncs.com
DM_TIMEOUT_SECONDS=10.0

# [可选] SMTP 备用
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=xxxxxxxxxx@qq.com
SMTP_PASSWORD=xxxxxxxxxxxxxxxx
SMTP_FROM_NAME=XX租房
SMTP_FROM_EMAIL=xxxxxxxxxx@qq.com
SMTP_USE_TLS=true
SUPPORT_EMAIL=xxxxxxxxxx@qq.com

# ═══════════════════════════════════════════════════════════
# 微信开放平台（Web 扫码登录）
# ═══════════════════════════════════════════════════════════
WECHAT_OPEN_APPID=wxXXXXXXXXXXXXXXXX
WECHAT_OPEN_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_OPEN_REDIRECT_URI=https://your-domain.com/api/v1/auth/wechat/callback
WECHAT_OPEN_DEV_MODE=false

# ═══════════════════════════════════════════════════════════
# 基础配置
# ═══════════════════════════════════════════════════════════
DATABASE_URL=postgresql+asyncpg://rental:rental@localhost:5432/rental_housing
REDIS_URL=redis://localhost:6379/0
AUTH_SECRET_KEY=<生成随机字符串>
CORS_ORIGINS=["https://your-domain.com"]
FRONTEND_URL=https://your-domain.com
ENVIRONMENT=production
DEBUG=false
```

---

## 附录：前端环境变量

前端 `.env` 需单独配置以下变量：

```bash
# 高德地图 JS API Key（前端地图展示）
VITE_AMAP_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Google Maps JS API Key（前端地图展示）
VITE_GM_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

---

## 附录：不需要配置的项目

以下功能**本版不实现**，无需注册：

| 项目 | 说明 |
|------|------|
| 微信小程序 | 本版仅 Web 端，小程序暂不交付 |
| WECHAT_APPID / WECHAT_SECRET | 小程序凭证，无需配置 |
| 微信支付 | 本版使用模拟支付，生产上线前再配置 |
| 支付宝支付 | 同上 |
| 银行卡支付 | 同上 |

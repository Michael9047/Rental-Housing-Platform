# AI全球公寓租赁平台 — 前端实现总纲 v2.0

> **更新日期**：2026-06-26（已合并 main 分支最新代码）  
> **代码量**：~16,500行 | **文件数**：55+ | **技术栈**：Vue 3.5 + TS 5.6 + Element Plus 2.9 + Pinia 2.3 + Leaflet + AMap JS API 2.0  
> **后端新增**：地理编码 · 支付服务 · 短信/邮件 · 评价/收藏/广告模型 · uhomes 设计系统  
> **用途**：AI 或开发人员可从零构建完整前端项目。每个页面、组件、数据流均有明确规格。

---

## 目录

1. [项目骨架](#一项目骨架) — 文件清单、入口、根组件、包依赖
2. [路由表](#二路由表) — 26条路由、守卫、参数传递
3. [布局框架](#三布局框架) — 租客/房东双角色侧边栏分离
4. [公共组件](#四公共组件) — PropertyCard、BookingDateDialog、GlobalFooter
5. [首页](#五首页) — Hero区、搜索条、地区卡片、精选房源
6. [搜索结果页](#六搜索结果页) — 筛选器、AI搜索、分页
7. [公寓详情页](#七公寓详情页) — 图片轮播、设施、地图、POI、评价
8. [预约流程](#八预约流程) — 日期弹窗→确认页→待支付→押金支付→电子合同
9. [租客个人中心](#九租客个人中心) — 7Tab完整页面
10. [公寓管理员后台](#十公寓管理员后台) — 8Tab运营工作台
11. [登录注册](#十一登录注册) — 表单校验、Token管理
12. [辅助页面](#十二辅助页面) — 通知、编辑资料、地图找房
13. [数据层](#十三数据层) — Axios拦截器、Pinia Store、TypeScript类型
14. [设计规范](#十四设计规范) — 颜色、圆角、阴影、按钮、表格
15. [后端接口对照](#十五后端接口对照) — 42个API、前端自处理数据
16. [附录](#十六附录) — 已解决问题、待后端补充字段

---

## 一、项目骨架

### 1.1 包依赖

```json
{
  "dependencies": {
    "vue": "3.5",
    "vue-router": "4.5",
    "pinia": "2.3",
    "axios": "1.7",
    "element-plus": "2.9",
    "@element-plus/icons-vue": "2.3",
    "leaflet": "1.9",
    "@types/leaflet": "1.9"
  },
  "devDependencies": {
    "vite": "6",
    "vue-tsc": "2",
    "typescript": "5.6",
    "@vitejs/plugin-vue": "5",
    "vitest": "2"
  }
}
```

### 1.2 环境配置 `vite.config.ts`

```typescript
// dev server 端口 5173，@ 别名指向 src/
// /api 代理到 http://localhost:8000
export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': resolve(__dirname, 'src') } },
  server: { port: 5173, proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } }
})
```

### 1.3 入口文件 `main.ts`

```typescript
// 1. createApp(App)
// 2. createPinia() → app.use
// 3. router → app.use
// 4. ElementPlus({ locale: zhCn }) → app.use
// 5. 全局注册所有 Element Plus 图标:
//    for (const [key, component] of Object.entries(ElementPlusIconsVue))
//      app.component(key, component)
```

### 1.4 根组件 `App.vue`

```css
/* 全局 CSS 变量定义 */
--primary: #FF6B35; --primary-light: #FFF4ED; --primary-dark: #E85D2C;
--success: #67c23a; --warning: #e6a23c; --danger: #f56c6c;
--bg: #f5f6f8; --bg-white: #ffffff;
--text-primary: #303133; --text-secondary: #606266; --text-muted: #909399;
--border: #e4e7ed; --border-light: #ebeef5;
--radius: 12px; --radius-sm: 8px; --radius-lg: 16px;
--shadow: 0 2px 12px rgba(0,0,0,0.06); --shadow-sm: 0 1px 4px rgba(0,0,0,0.04);

/* Element Plus 全局覆盖 */
--el-color-primary: #FF6B35;
--el-color-primary-light-3: #FF8F64;
--el-color-primary-light-5: #FFA982;
--el-color-primary-light-7: #FFC7AD;
--el-color-primary-light-9: #FFF4ED;
--el-color-primary-dark-2: #E85D2C;
--el-border-radius-base: 8px;
--el-border-radius-round: 20px;
```

模板仅为 `<div id="app"><router-view /></div>`。

### 1.5 完整文件清单

```
frontend/src/
├── App.vue                           # 全局 CSS 变量 + Element Plus 覆盖
├── main.ts                           # 入口：挂载 Pinia/Router/ElementPlus/图标
├── components/
│   ├── PropertyCard.vue              # 房源卡片（317行）— 项目复用最广的组件
│   ├── BookingDateDialog.vue         # 预约日历弹窗（289行）— 禁用过去日期
│   ├── AmapMap.vue                   # 高德地图组件（198行）🆕 — 房源详情地图展示
│   └── GlobalFooter.vue              # 全局页脚（78行）
├── layouts/
│   └── DefaultLayout.vue             # 双角色侧边栏布局（370行）
├── router/
│   └── index.ts                      # 26条路由 + 4级守卫
├── services/                         # 10个API模块
│   ├── api.ts                        #   Axios: baseURL + token拦截器 + 401跳转
│   ├── auth.ts                       #   登录/注册/微信/getMe
│   ├── property.ts                   #   房源CRUD + 搜索 + 图片 + POI
│   ├── booking.ts                    #   预订CRUD + 取消
│   ├── payment.ts                    #   支付创建/查询/回调
│   ├── contract.ts                   #   合同生成/签署/下载
│   ├── user.ts                       #   用户资料更新
│   ├── chat.ts                       #   AI聊天
│   ├── notification.ts               #   通知列表/标记已读/未读数
│   └── admin.ts                      #   管理后台统计
├── stores/
│   ├── auth.ts                       #   登录状态: user/token/isLoggedIn/isLandlord
│   └── property.ts                   #   房源数据: properties/searchResults/currentProperty
├── types/
│   ├── property.ts                   #   Property, PropertySearchParams, PropertyImage 等
│   ├── booking.ts                    #   Booking, BookingCreate, Notification
│   ├── user.ts                       #   User, UserRole
│   ├── auth.ts                       #   LoginRequest, RegisterRequest, TokenResponse
│   ├── chat.ts                       #   ChatSession, ChatMessage
│   └── admin.ts                      #   AdminStats
└── views/
    ├── Home.vue                      # 首页（718行）
    ├── Search.vue                    # 搜索结果页（488行）
    ├── PropertyDetail.vue            # 公寓详情（886行）
    ├── BookingConfirm.vue            # 预约信息填写（253行）— 已移除支付步骤
    ├── PendingPayment.vue            # 待支付订单详情（200行）🆕
    ├── DepositPayment.vue            # 押金支付页（210行）🆕 双币种
    ├── ContractView.vue              # 电子合同查看/下载（220行）🆕
    ├── Profile.vue                   # 租客个人中心（490行）🆕 7Tab
    ├── ProfileEdit.vue               # 个人资料编辑页（180行）🆕
    ├── AdminWorkspace.vue            # 公寓管理员后台（750行）🆕 8Tab
    ├── TenantBookings.vue            # 租客预订列表（195行）
    ├── LandlordBookings.vue          # 房东预订管理（163行）
    ├── CreateProperty.vue            # 发布/编辑房源（423行）
    ├── ManageProperties.vue          # 房源管理列表（155行）
    ├── PropertyImages.vue            # 房源图片管理（520行）
    ├── Notifications.vue             # 通知列表（120行）
    ├── MapSearch.vue                 # 地图找房（240行）🆕 Leaflet + 世界地图
    ├── Login.vue                     # 登录页（203行）
    ├── Register.vue                  # 注册页（181行）
    └── admin/
        ├── AdminDashboard.vue        # 管理员仪表盘（119行）
        ├── AdminUsers.vue            # 用户管理（84行）
        ├── AdminProperties.vue       # 房源审核（101行）
        ├── AdminImport.vue           # CSV/Excel批量导入（534行）
        ├── AdminLogs.vue             # 审计日志（110行）
        └── AdminEmbeddings.vue       # 向量嵌入管理（124行）
```

### 1.6 页面跳转关系

```
                    ┌──────────┐
           ┌───────│ 登录/注册  │
           │       └────┬─────┘
           ▼            │
     ┌──────────┐       │
     │   首页    │◄──────┘
     │  /       │
     └────┬─────┘
          │ AI搜索 / 地区卡片 / 标签
          ▼
     ┌──────────┐   点击卡片     ┌──────────────┐
     │ 搜索结果页 │─────────────►│  公寓详情页    │
     │ /search  │◄──返回        │ /property/:id │
     └────┬─────┘               └──────┬───────┘
          │ 一键预订                    │ 预约看房弹窗
          ▼                             ▼
     ┌──────────────────┐     ┌─────────────────────┐
     │ 预约确认页         │     │ BookingDateDialog    │
     │ /booking/confirm  │◄────│ (弹窗组件,禁用过去日期) │
     └────────┬─────────┘     └─────────────────────┘
              │ 提交成功
              ▼
     ┌──────────────────┐
     │  租客个人中心      │
     │  /profile        │
     │  ├ 看房预约        │──确认租房──→ /booking/payment/:id ──支付押金──→ /booking/payment/:id/deposit
     │  ├ 我的合同        │─────────────────────────────────────────→ /contract/:id
     │  ├ 收藏房源        │
     │  ├ 我的账单        │──待支付/已支付
     │  ├ 报修           │
     │  ├ 消息           │
     │  └ 设置           │
     └──────────────────┘

     ┌──────────────────┐
     │ 公寓管理员后台     │  (房东/管理员角色)
     │  /workspace      │
     │  ├ 房源管理        │
     │  ├ 预约管理        │
     │  ├ 合约管理        │
     │  ├ 财务中心        │
     │  ├ 租客管理        │
     │  ├ 维修工单        │
     │  ├ 消息中心        │
     │  └ 门店设置        │
     └──────────────────┘

     ┌──────────┐
     │ 地图找房  │  /map — Leaflet + OpenStreetMap, 全球视野, 自由缩放
     └──────────┘
```

---

## 二、路由表

### 2.1 全部路由（26条）

| 路径 | 组件 | 需登录 | 角色 | meta |
|------|------|:---:|------|------|
| `/` | Home.vue | | | |
| `/search` | Search.vue | | | |
| `/map` | MapSearch.vue | | | 🆕 |
| `/property/:id` | PropertyDetail.vue | | | |
| `/login` | Login.vue | | 已登录→回首页 | `guest:true` |
| `/register` | Register.vue | | 已登录→回首页 | `guest:true` |
| `/profile` | Profile.vue | ✅ | 租客 | `requiresAuth` |
| `/profile/edit` | ProfileEdit.vue | ✅ | | `requiresAuth` 🆕 |
| `/workspace` | AdminWorkspace.vue | ✅ | landlord/admin | `requiresLandlord` 🆕 |
| `/booking/confirm` | BookingConfirm.vue | ✅ | | `requiresAuth` |
| `/booking/payment/:id` | PendingPayment.vue | ✅ | | `requiresAuth` 🆕 |
| `/booking/payment/:id/deposit` | DepositPayment.vue | ✅ | | `requiresAuth` 🆕 |
| `/contract/:id` | ContractView.vue | ✅ | | `requiresAuth` 🆕 |
| `/bookings/tenant` | TenantBookings.vue | ✅ | | `requiresAuth` |
| `/bookings/landlord` | LandlordBookings.vue | ✅ | landlord/admin | `requiresLandlord` |
| `/property/create` | CreateProperty.vue | ✅ | landlord/admin | `requiresLandlord` |
| `/property/manage` | ManageProperties.vue | ✅ | landlord/admin | `requiresLandlord` |
| `/property/:id/edit` | CreateProperty.vue | ✅ | landlord/admin | `requiresLandlord` |
| `/property/:id/images` | PropertyImages.vue | ✅ | landlord/admin | `requiresLandlord` |
| `/notifications` | Notifications.vue | ✅ | | `requiresAuth` |
| `/admin` | AdminDashboard.vue | ✅ | admin | `requiresAdmin` |
| `/admin/users` | AdminUsers.vue | ✅ | admin | `requiresAdmin` |
| `/admin/properties` | AdminProperties.vue | ✅ | admin | `requiresAdmin` |
| `/admin/logs` | AdminLogs.vue | ✅ | admin | `requiresAdmin` |
| `/admin/embeddings` | AdminEmbeddings.vue | ✅ | admin | `requiresAdmin` |
| `/admin/import` | AdminImport.vue | ✅ | admin | `requiresAdmin` |

### 2.2 路由守卫

```typescript
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const userStr = localStorage.getItem('user')
  let user: { role: string } | null = null
  try { if (userStr) user = JSON.parse(userStr) } catch { /* ignore */ }

  if (to.meta.requiresAuth && !token) return next({ name: 'login', query: { redirect: to.fullPath } })
  if (to.meta.guest && token) return next({ name: 'home' })
  if (to.meta.requiresLandlord && user?.role !== 'landlord' && user?.role !== 'admin') return next({ name: 'home' })
  if (to.meta.requiresAdmin && user?.role !== 'admin') return next({ name: 'home' })
  next()
})
```

### 2.3 页面间参数传递

| 跳转来源 | 跳转目标 | 方式 | 参数 |
|---------|---------|------|------|
| 首页搜索框 | `/search` | query | `?q=关键词` |
| 首页地区卡片 | `/search` | query | `?country=china` |
| PropertyCard | `/property/:id` | params | `:id` |
| 预约弹窗确认 | `/booking/confirm` | query | `?property_id=&date=&slot=` |
| 预订列表→确认租房 | `/booking/payment/:id` | params | `:id` (booking id) |
| 待支付→支付 | `/booking/payment/:id/deposit` | params | `:id` |
| 支付中心→合同 | `/contract/:id` | params | `:id` |
| 个人中心 | `/profile` | query | `?tab=bookings\|contracts\|favorites\|bills\|repairs\|messages\|settings` |
| 编辑资料 | `/profile/edit` | — | — |

---

## 三、布局框架

### 3.1 DefaultLayout.vue — 双角色侧边栏

所有页面（除 login/register）共用。关键变化：**租客和房东看到完全不同的侧边栏和Header下拉菜单**。

#### Header 结构

```
┌──────────────────────────────────────────────────────────────┐
│ 🏠 AI全球公寓租赁  │ 全局搜索条(圆角36px) │ [角色标签] [🔔] [头像▼] │
└──────────────────────────────────────────────────────────────┘
```

**Header 右侧（登录状态）：**
- 管理员显示 `el-tag type="danger"` "管理员"
- 房东显示 `el-tag type="warning"` "公寓运营商"
- 租客显示 `el-tag type="info"` "租客"
- 铃铛按钮 + `el-badge` 显示未读数（通过 `watch(route)` 实时刷新）
- 头像下拉菜单：

  **租客菜单：** 个人中心 | 我的预订

  **房东/管理员菜单：** 运营工作台 | 预约管理 | 房源管理 | 发布房源

  **管理员额外：** 系统管理

#### Sidebar 结构

```typescript
// 模板中用 v-if 区分两个完全不同的菜单：

// ==== 租客侧边栏 ====
<template v-if="!authStore.isLandlord && !authStore.isAdmin">
  首页 / 搜索房源 / 地图找房 / 我的预订 / 个人中心
</template>

// ==== 房东/管理员侧边栏 ====
<template v-if="authStore.isLandlord || authStore.isAdmin">
  首页 / 运营工作台 / 房源管理 / 发布房源 / 预约管理 / 消息通知
  // 管理员额外：
  系统管理 → 仪表盘/用户管理/房源审核/数据导入/审计日志/Embedding
</template>
```

**activeMenu 计算规则：**
```typescript
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/admin')) return path
  if (path.startsWith('/notifications')) return '/notifications'
  if (path.startsWith('/property/')) return path === '/property/create' ? '/property/create' : '/property/manage' ? '/property/manage' : '/search'
  if (path.startsWith('/bookings/')) return path
  if (path.startsWith('/workspace')) return '/workspace'
  return path
})
```

**notification badge 刷新机制：**
```typescript
// onMounted 时首次获取
// watch(route.path) 每次路由变化重新获取（读完通知回来自动刷新）
async function fetchUnreadCount() {
  if (!authStore.isLoggedIn) return
  const resp = await notificationService.getUnreadCount()
  unreadCount.value = resp.count
}
```

### 3.2 GlobalFooter.vue

```html
底部栏（margin-top:auto 推到底）：
🏠 AI国内租房检索 ｜ 🌍 海外留学生公寓预订 ｜ 💰 线上押金支付 ｜ 📄 电子合同签署 ｜ 🎓 签证租房咨询
客服中心 ｜ 平台规则 ｜ 隐私政策 ｜ © 2026 AI全球公寓租赁平台
```

---

## 四、公共组件

### 4.1 PropertyCard `components/PropertyCard.vue` (317行)

**复用范围：** 首页精选、搜索结果网格、详情页相似房源、用户中心收藏

**Props：**
```typescript
{
  property: Property | PropertySearchResult,
  showSimilarity?: boolean,  // 显示AI匹配度徽章
  showQuickBook?: boolean,   // 显示"一键预订"按钮
}
```

**Events：** `@book(property)` — 点击一键预订

**内部结构：**
```
┌─ 封面图（200px）──────────────────────┐
│  [图片] [匹配度徽章▸左上] [地区标签▸右下] │
└──────────────────────────────────────┘
┌─ 信息区 ─────────────────────────────┐
│  标题（单行截断）                      │
│  [公寓] [2室1卫] [80㎡]                │
│  [电梯] [空调] [WiFi] ... (金色标签)    │
│  📍 地址                              │
│  ¥2,500/月    [查看详情] [一键预订]    │
└──────────────────────────────────────┘
```

**配套标签推断规则：**
```typescript
// 根据 district 推断城市标签
// 根据 property_type: apartment→电梯+WiFi, studio→独立卫浴
// 根据 bedrooms≥2 → 近地铁
// 根据 price_monthly: <3000→平价好房, >8000→精装修
// 根据 description 关键词: 短租/宠物/暖气
// 去重取前5个
// 颜色: bg:#fdf6ec, border:#f5dab1, color:#b88230
```

### 4.2 BookingDateDialog `components/BookingDateDialog.vue` (289行)

**日期禁用规则（完整实现）：**
```typescript
// 1. 使用 computed setter 拦截 v-model
const selectedDate = computed({
  get: () => _selectedDate.value,
  set: (val: Date) => {
    const old = _selectedDate.value
    const monthChanged = val.getFullYear() !== old.getFullYear() || val.getMonth() !== old.getMonth()
    if (monthChanged) {
      // 切换月份：允许（即使切换到了过去月份）
      // 如果日期在过去，设为该月1号（仅显示，不选中具体日）
      if (isPastDay(val)) {
        _selectedDate.value = new Date(val.getFullYear(), val.getMonth(), 1)
      } else {
        _selectedDate.value = val
      }
    } else {
      // 同月选中：只允许今天及未来
      if (!isPastDay(val)) _selectedDate.value = val
    }
  },
})

// 2. CSS 辅助
.calendar-day.past {
  color: var(--border);
  cursor: not-allowed;
  pointer-events: none;  // 阻止点击冒泡
}

// 3. 确认时双重校验
async function handleConfirm() {
  if (!canConfirm.value) return
  if (isPastDay(selectedDate.value)) return  // 二次拦截
  // ... emit confirm
}

// 4. 弹窗打开时重置为今天
watch(visible, (v) => { if (v) { _selectedDate.value = new Date(); selectedSlot.value = '' } })
```

**时间槽：** 上午(9-12) / 下午(14-17) / 晚间(19-21) — 三个卡片，橙色选中态。

**emit：** `@confirm({ propertyId, date: 'YYYY-MM-DD', slot: 'morning'|'afternoon'|'evening' })`

---

## 五、首页

### 5.1 文件 `views/Home.vue` (718行)

### 5.2 结构

```
Hero 区域：
  [🤖 AI驱动]  大标题"AI智能找公寓"  副标题描述
  ┌──────────────────────────────────────────┐
  │ 🔍 输入需求...             │ 🎤 │ 搜索   │
  └──────────────────────────────────────────┘
  [单间公寓] [一居室] [两居室] [海外留学生公寓] [地铁好房] [短租] [宠物友好]

按地区找房（横向滚动）：
  ◀ [国内城区] [🇸🇬新加坡] [🇭🇰香港] [🇦🇺澳洲] [🇬🇧英国留学] [🇺🇸美国] [🌸日韩] [🇪🇺欧洲] [＋更多] ▶

AI精选房源列表（最多6条）：
  每项：左图280px + 标题 + 匹配度 + 户型/面积 + 配套标签 + 地址 + ¥月租 + [查看详情] [一键预订]
```

### 5.3 数据来源

```typescript
propertyStore.fetchList({ limit: 6 })  →  GET /api/v1/properties?limit=6

// 地区列表（静态常量）
const regions = [
  { value:'china', label:'国内城区', icon:'🏙️' },
  { value:'singapore', label:'新加坡', icon:'🇸🇬' },
  { value:'hongkong', label:'香港公寓', icon:'🇭🇰' },
  { value:'australia', label:'澳洲房源', icon:'🇦🇺' },
  { value:'uk', label:'英国留学', icon:'🇬🇧' },
  { value:'usa', label:'美国房源', icon:'🇺🇸' },
  { value:'japan_korea', label:'日韩房源', icon:'🌸' },
  { value:'europe', label:'欧洲公寓', icon:'🇪🇺' },
]

// 快捷标签
const quickTags = ['单间公寓','一居室','两居室','海外留学生公寓','地铁好房','短租','宠物友好']
```

### 5.4 语音输入

```typescript
// Web Speech API, lang='zh-CN'
// 不支持时 ElMessage.warning('当前浏览器不支持语音识别')
// 监听中时橙色脉冲动画，结果填充到搜索框
```

---

## 六、搜索结果页

### 6.1 文件 `views/Search.vue` (488行)

### 6.2 筛选器

| 字段 | 组件 | 说明 |
|------|------|------|
| AI搜索 | el-input | 自然语言，pgvector语义匹配 |
| 搜索模式 | el-switch | 语义匹配 / 精确检索 |
| 国家 | el-select | 8选项，选中后出现城市/海外 |
| 城市(国内) | el-select | 仅选国内时显示 |
| 海外地区 | el-select | 根据国家动态展示 |
| 价格 | el-input-number×2 | 最低~最高 |
| 户型 | el-select | 1室/2室/3室/4室+ |
| 类型 | el-select | 公寓/别墅/单间/合租 |
| 排序 | el-select | 匹配度/价格↑/价格↓/面积↓ |

> ⚠️ `country`、`overseas_area` 后端不支持，前端映射到 `district` 参数。

### 6.3 搜索逻辑

```typescript
function doSearch() {
  const params = {
    q: semanticMode ? filters.q : undefined,
    district: filters.district || filters.overseas_area || filters.country,
    price_min, price_max, bedrooms, property_type,
    limit: 30,
  }
  propertyStore.fetchSearch(params)  // GET /api/v1/properties/search
}
```

### 6.4 分页

- pageSize = 6
- `el-pagination`, layout="prev, pager, next", background
- 空状态：`el-empty` "暂无匹配房源" + "一键放宽条件"按钮

---

## 七、公寓详情页

### 7.1 文件 `views/PropertyDetail.vue` (886行)

### 7.2 结构

```
顶栏: ← 返回 | ⭐ 收藏 | 📤 分享
图片轮播: el-carousel 420px + 缩略图条
头部: 标题 + [可租] [公寓] + 地址 + ¥月租 + 押金 + 服务费率 + [预约看房]
四宫格: 📐户型 | 📏面积 | 🏢类型 | ✅状态
描述: 长文本 pre-wrap
设施: 🏠基础(电梯空调冰箱...) + 🌍海外专属(健身房自习室签证...)
地图: AmapMap.vue 高德组件 360px（VITE_AMAP_KEY 配置后启用，否则降级 OpenStreetMap）
AI周边: POI卡片(从 /pois/:id 加载) + 后端已实现 AmapGeocodingService
评价: 后端 Review 模型已建（`backend/app/models/review.py`），前端待对接
相似房源: 3列 PropertyCard 网格
悬浮底栏: [返回] [立即支付押金预订]
```

### 7.3 设施推断规则

```typescript
// 基础（所有房源）: 电梯 空调 洗衣机 冰箱 WiFi 暖气
// house → +车位 +全屋家电
// studio → +独立卫浴 +储物间
// area>60㎡ → +阳台
// description含宠物/猫/狗 → +可养宠物
// 海外房源（district不含中国城市）→ +健身房 自习室 签证咨询 24h前台 校车接驳
```

### 7.4 评价 mock

```typescript
const reviews = [
  { user:'李明', avatar:'李', avatarColor:'#FF6B35', rating:5, date:'2026-06-20',
    text:'房间很干净，采光好...', reply:'感谢李先生的认可' },
  // ... 共4条
]
```

---

## 八、预约流程

### 8.1 完整流程图

```
房源详情页 → [预约看房] → BookingDateDialog（禁用过去日期）
                ↓ 选日期+时间段, 点下一步
         /booking/confirm?property_id=&date=&slot=
                ↓ 填姓名+手机+留言, 点提交预约
         直接保存到后端 → ElMessage.success → 跳转到个人中心
                ↓
         个人中心「看房预约」→ [确认租房]
                ↓
         /booking/payment/:id （待支付订单详情页）
         ┌─ 完整展示：订单号/房源编号/预约时间/租客信息/押金
         └─ [支付押金] 按钮
                ↓
         /booking/payment/:id/deposit （押金支付页）
         ┌─ 押金金额（大号红色数字）
         ├─ 双币种：人民币 ¥6,500 / 美元 $896.55
         ├─ 支付方式：💚微信 / 💙支付宝
         └─ [确认支付] → 调用 paymentService.create → callback → 成功
                ↓
         ElMessage.success → 跳转 个人中心「支付中心」
                ↓
         个人中心「我的账单」→ [查看合同]
                ↓
         /contract/:id （电子合同页）
         ┌─ 合同编号 + 双方信息 + 押金条款 + 租赁条款
         └─ [下载PDF] 按钮
```

### 8.2 BookingConfirm.vue (253行) — 预约确认页

**简化设计（移除支付步骤）：**
- 无步骤条，直接填写表单
- 提交后调用 `bookingService.create()` → 保存到后端
- 成功后 `ElMessage.success` + `setTimeout(() => router.push('/profile?tab=bookings'), 1500)`
- **不再跳转到支付页**，预约和支付解耦

**表单字段：**
| 字段 | 组件 | 校验 |
|------|------|------|
| 看房日期 | el-date-picker | `:disabled-date` 禁用过去 |
| 时间段 | el-select | 上午/下午/晚间 |
| 姓名 | el-input | 必填 |
| 手机号 | el-input | 必填 + `^1[3-9]\d{9}$` |
| 留言 | el-input textarea | 选填 |

**time_slot 处理：** 拼入 message: `【看房时段：下午 14:00-17:00】\n${留言内容}`

**右侧：** 房源信息卡（封面图+标题+地址+标签+月租+押金）

**错误处理：**
```typescript
catch (err) {
  if (status === 409) ElMessage.warning('您已对该房源发起过预约')
  else if (status === 403) ElMessage.error('仅租客身份可预约看房')
  else if (status === 401) ElMessage.error('请先登录')
  else if (detail) ElMessage.error(detail)
  else ElMessage.error('预约提交失败，请重试')
}
```

### 8.3 PendingPayment.vue (200行) — 待支付订单详情

**路由：** `/booking/payment/:id`

**内容：**
- 预约信息卡：订单编号 / 房源编号 / 预约日期 / 订单状态 / 押金状态 / 押金额 / 服务费
- 租客信息卡：租客ID / 房东ID
- 房源信息卡：封面图 + 标题 + 地址 + 标签 + 月租
- **底部悬浮栏：** `[支付押金]` 橙色圆角大按钮 → 跳转 `/booking/payment/:id/deposit`

### 8.4 DepositPayment.vue (210行) — 押金支付页

**双币种展示：**
```
        ┌──────────────────────┐
        │      💰 押金金额        │
        │                      │
        │    ¥6,500            │  ← 48px 粗体红色
        │                      │
        │ 人民币 CNY: ¥6,500    │
        │ 美元   USD: $896.55  │  ← 按汇率 ≈7.25 换算
        └──────────────────────┘
```

**支付方式：** 微信支付 💚 / 支付宝 💙 — 卡片选择，active 态橙色边框+浅橙背景

**支付逻辑：**
```typescript
async function doPayment() {
  await paymentService.createPayment({ booking_id, amount: depositAmount })
  // 模拟 callback 成功
  paySuccess = true
}
```

**成功后：** `el-result` success → 两个按钮："查看支付中心(`/profile?tab=contracts`)" / "返回首页"

### 8.5 ContractView.vue (220行) — 电子合同

**路由：** `/contract/:id`

**结构：**
```
┌─ 合同卡片（带水印"电子合同"）────┐
│ 房屋租赁押金合同                   │
│ 合同编号：HT00000006              │
│ ─────────────────────            │
│ 第一条 租赁双方信息                │
│  出租方 #1 | 承租方 xxx | 房源 #1  │
│ ─────────────────────            │
│ 第二条 押金条款                    │
│  押金 ¥6,500 | 已支付 | 流水号    │
│  条款：转首期租金/全额退还/取消政策 │
│ ─────────────────────            │
│ 第三条 租赁基本条款                │
│ ─────────────────────            │
│ 第四条 其他约定                    │
└────────────────────────────────┘
[📥 下载电子合同 (PDF)]  ← 居中蓝色按钮
```

**下载：** `window.print()`（生产环境接后端PDF生成）

---

## 九、租客个人中心

### 9.1 文件 `views/Profile.vue` (490行) — 完全重写版

### 9.2 页面结构

```
┌─ 用户信息卡 ──────────────────────────────────┐
│ [头像64px] 用户名 [租客] [✓已实名]              │
│ 📧 email  📱 138**** ✳ 注册于2025-06-01         │
│ [编辑资料→/profile/edit] [实名认证弹窗]          │
└───────────────────────────────────────────────┘

┌─ 4个统计卡片（点击跳转对应Tab）─────────────────┐
│ 📅 看房预约:3 │ 💳 待支付:1 │ 📄 我的合同:2 │ ❤️ 收藏:5 │
└───────────────────────────────────────────────┘

┌─ 7个Tab ─────────────────────────────────────┐
│ [📅看房预约] [📄我的合同] [❤️收藏] [💳我的账单] [🔧报修] [🔔消息] [⚙️设置] │
└───────────────────────────────────────────────┘
```

### 9.3 Tab 详细规格

#### Tab1: 看房预约

- 筛选：全部 / 待房东确认 / 已同意 / 已取消 / 已完成
- 列表：房源 #、看房时间、状态、押金、操作
- 操作：pending → 取消预约 / pending\|approved → 确认租房
- 确认租房 → `router.push('/booking/payment/' + booking.id)`
- **过滤规则：已支付押金的订单不在此显示（移到支付中心）**

#### Tab2: 我的合同

- 筛选：生效中 / 快到期了 / 已结束
- 列表：房源、租期、月租金、押金、签约时间、状态
- 操作：查看合同 → `/contract/:id` / 下载
- **数据来源：筛选 deposit_status 为 paid/confirmed 的 booking**

#### Tab3: 收藏

- 3列 PropertyCard 网格
- 空状态："还没有收藏，去逛逛吧" → 跳 `/search`

#### Tab4: 我的账单（简化版）

- 子Tab：待支付 / 已支付
- **待支付：** 卡片式列表，每条显示 🏠 房源 + 押金额 + "支付后自动生成租房合同" + [去支付]
- **已支付：** 卡片式列表，绿色背景，显示 ✅已付 + [查看合同]
- ~~无"收支流水""租金账单"等复杂财务术语~~

#### Tab5: 报修

- [我要报修] 按钮 → 弹窗：选房源 + 选类型 + 描述
- 列表：工单号 / 房源 / 问题 / 时间 / 状态（待处理/维修中/已完成）

#### Tab6: 消息

- 左半：💬 房东消息 — 卡片列表
- 右半：🔔 系统通知 — 预约通过/押金到账等

#### Tab7: 设置

- 账号安全：手机号 / 密码 / 微信绑定
- 实名认证：上传身份证
- 通知设置：App内通知 / 短信提醒
- 帮助：联系客服 / 常见问题

### 9.4 数据流

```typescript
onMounted:
  authStore.fetchCurrentUser()    // GET /auth/me
  bookings = (await bookingService.list())  // GET /bookings
    .filter(b => b.deposit_status !== 'paid' && b.deposit_status !== 'confirmed')
  favorites = await propertyService.list({ limit: 6 })  // 暂用list代替
```

---

## 十、公寓管理员后台

### 10.1 文件 `views/AdminWorkspace.vue` (750行)

### 10.2 访问

- 路由：`/workspace`
- 权限：`requiresLandlord`（房东或管理员）
- 侧边栏入口：房东角色 → "运营工作台"

### 10.3 页面结构

```
┌─ 管理员信息卡 ───────────────────────────────┐
│ [头像64px] 张经理 [公寓运营管理员] [✓企业认证]  │
│ 📧 zhang@rental.com 📱 139**** 🏢负责:朝阳·海淀 │
│ [编辑资料] [资质上传]                           │
└──────────────────────────────────────────────┘

┌─ 6个统计卡片（点击跳转对应Tab）──────────────┐
│ 🏠管理房源:48 │ 📅待处理:8 │ 💰本月应收:¥98,500 │ 📄合同:35 │ 🔧工单:4 │ 👁️今日访客:156 │
└──────────────────────────────────────────────┘

┌─ 8个Tab ───────────────────────────────────┐
│ [🏠房源管理] [📅预约管理] [📄合约管理] [💰财务中心] [👥租客管理] [🔧维修工单] [💬消息中心] [⚙️门店设置] │
└──────────────────────────────────────────────┘
```

### 10.4 Tab 详细规格

| Tab | 筛选 | 核心功能 | Mock数据 |
|-----|------|---------|---------|
| 🏠房源管理 | 全部/空置/已租/维护/待上架 | 批量新增/上架/下架、编辑、维修标记、查看预约 | 7条 |
| 📅预约管理 | 全部/待审核/已同意/已拒绝 | 确认/驳回、批量发提醒、租客详情、已接待标记 | 4条 |
| 📄合约管理 | 生效中/即将到期/待续签/已解约 | 批量生成合同/导出/续租、查看/解约 | 4条 |
| 💰财务中心 | 定金/租金/收支明细/提现 | 月度报表导出 | 4条流水 |
| 👥租客管理 | — | 详情/缴费记录/报修历史 | 3条 |
| 🔧维修工单 | — | 派单/完成/上传凭证 | 3条 |
| 💬消息中心 | — | 租客咨询(左) + 系统通知(右) | 各3条 |
| ⚙️门店设置 | — | 账号安全/对公收款/资质管理/推送开关 | — |

### 10.5 弹窗

- **编辑资料：** 头像上传 + 工作手机 + 收款账户 + 运营简介
- **资质上传：** 营业执照 + 产权合规材料 + 身份证核验

---

## 十一、登录注册

### 11.1 Login.vue (203行)

**关键修复：按钮放在 `<el-form>` 外部，使用本地 `loading` 状态而非 `authStore.loading`**

```vue
<el-form ref="formRef" :model="form" :rules="rules" label-position="top">
  <el-form-item label="用户名或邮箱" prop="username_or_email">
    <el-input v-model="form.username_or_email" />
  </el-form-item>
  <el-form-item label="密码" prop="password">
    <el-input v-model="form.password" type="password" @keyup.enter="handleLogin" />
  </el-form-item>
</el-form>
<!-- 按钮在表单外！ -->
<el-button type="primary" :loading="loading" @click="handleLogin">登录</el-button>
```

**登录流程：**
```typescript
async function handleLogin() {
  await formRef.value.validate()
  loading.value = true
  try {
    await authStore.login({ username_or_email, password })
    // authStore.login 内部流程:
    //   1. authService.login() → token
    //   2. authService.getMe() → user
    //   3. setAuth(token, user) → 更新 Pinia 响应式状态 + localStorage
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (err) {
    ElMessage.error(detail || '登录失败')
  } finally { loading.value = false }
}
```

**视觉：** 蓝紫渐变背景 + 卡片居中 + LOGO + 微信登录按钮（绿色）

### 11.2 Register.vue (181行)

同样按钮在表单外。默认选中"租客"。

**注册流程：** `authStore.register()` → 成功后 `router.push('/login')`

### 11.3 后端对应修复

**`LoginRequest` Schema 修复（Pydantic ValueError 序列化崩溃）：**
```python
# 修复前：model_validator 抛 ValueError → json.dumps 崩溃 → 500
# 修复后：简化 Schema
class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)
```

**`_build_error_response` 修复：**
```python
# 安全序列化 Pydantic 错误对象
if isinstance(detail, str):
    safe_detail, safe_details = detail, None
else:
    safe_detail = str(detail)
    safe_details = [{"msg": str(e.get("msg","")), "loc": e.get("loc",[])} for e in detail]
```

---

## 十二、辅助页面

### 12.1 租客端辅助页

| 页面 | 行数 | 路由 | 功能 |
|------|:---:|------|------|
| TenantBookings.vue | 195 | `/bookings/tenant` | 租客预订列表（过滤已支付），确认租房按钮 |
| Notifications.vue | 120 | `/notifications` | 通知列表（无标题），点击标记已读 |
| ProfileEdit.vue | 180 | `/profile/edit` 🆕 | 独立编辑资料页，双重模式切换（查看/编辑） |
| MapSearch.vue | 240 | `/map` 🆕 | Leaflet世界地图，搜索定位，房源打点 |

### 12.2 地图找房 `MapSearch.vue`

```
┌─ 搜索栏 ──────────────────────────────────┐
│ 🔍 [输入国家/城市名…] [搜索] [🌍世界视图]    │
└───────────────────────────────────────────┘
┌─ 地图主体（Leaflet + OpenStreetMap）───────┐
│ 📍 北京  📍 东京  📍 巴黎                    │
│                       [当前区域6套房源▾]     │
│                       ┌─────────────────┐ │
│                       │ 房源卡片列表...   │ │
│                       └─────────────────┘ │
└───────────────────────────────────────────┘
```

**搜索功能：** 调用 Nominatim API 地理编码 → `map.flyTo()`

**Leaflet 初始化：**
```typescript
map = L.map('map', { center: [39.9042, 116.4074], zoom: 5 })
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map)
// 修复 Vite 打包默认图标问题
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({ iconUrl: markerIcon, iconRetinaUrl: markerIcon2x, shadowUrl: markerShadow })
setTimeout(() => map.invalidateSize(), 100)
```

**样式关键：** `height: calc(100vh - 64px - 48px); margin: -24px` — 填满布局内容区

### 12.3 地图找房增强方案（待实现）🔮

> 当前状态：仅基础打点+搜索。以下为参考美团/贝壳找房地图体验的完整增强方案。

#### 12.3.1 整体交互架构

```
┌─ 顶部悬浮搜索栏 ──────────────────────────┐
│ 🔍 [搜索框: 城市/区域/小区…]    [筛选🔽]    │
├───────────────────────────────────────────┤
│                                           │
│   🗺️ 地图主体                              │
│   ┌────┐                                  │
│   │¥6500│  ← 价格直接标在标记上              │
│   └────┘                                  │
│     📍📍📍                                │
│     📍(48)  ← 缩小后聚合成数字              │
│                                           │
│         ┌──────┐                          │
│         │ 🎯定位│  ← 右下角悬浮按钮组        │
│         │ 🔍搜此│                          │
│         │ 🏠列表│                          │
│         └──────┘                          │
│                                           │
│ ┌─ 底部抽屉列表 ──────────────────────────┐ │
│ │ 排序: 价格↑ ｜ 面积 ｜ 最新   共12套     │ │
│ │ ┌────────────────────────────────────┐ │ │
│ │ │ 🏠 朝阳精装两居  ¥6,500  [详情][收藏]│ │ │
│ │ │ 2室1卫·85㎡·朝阳区                    │ │ │
│ │ └────────────────────────────────────┘ │ │
│ │ ┌────────────────────────────────────┐ │ │
│ │ │ ... 更多房源 ...                     │ │ │
│ │ └────────────────────────────────────┘ │ │
│ └───────────────────────────────────────┘ │
│   半屏/全屏 可拖拽切换                       │
└───────────────────────────────────────────┘
```

#### 12.3.2 待实现功能清单

**🔴 P0 — 底部抽屉列表 + 拖拽**

三级高度切换：
```
收起态: 高 60px，显示 "当前区域 12 套房源 ▔"（可拖拽手势展开）
半屏态: 高 40vh，排序栏 + 卡片列表滚动，标记与列表双向联动
全屏态: 高 85vh，覆盖地图，纯列表浏览模式
```

双向联动逻辑：
- 列表项 hover → 地图对应标记放大/高亮
- 地图标记点击 → 列表自动滚动到对应项
- 列表项点击 → 地图 flyTo 该房源 + 弹出预览卡

实现方案：使用 `vue-draggable-resizable` 或手写 touch/mouse 事件，`transform: translateY` 做平滑动画。

**🔴 P0 — 筛选面板**

点击顶部 [筛选🔽] → 从上方滑入半透明面板：
```
┌──────────────────────────────────────┐
│ 价格范围: [____] ~ [____] 元/月       │
│ 户型: [全部] [1室] [2室] [3室] [4室+] │
│ 类型: [公寓] [别墅] [单间] [合租]      │
│ 面积: [50-80㎡] [80-120㎡] [120+]     │
│ 设施: [电梯] [空调] [暖气] [WiFi] ...  │
│ [重置]               [确认 (12套)]    │
└──────────────────────────────────────┘
```
筛选后：地图标记实时更新，列表重新排序。筛选参数传给 `/map/properties` 接口。

**🟡 P1 — 价格标签覆盖物**

用 Leaflet `DivIcon` 实现自定义标记：
```typescript
const priceIcon = L.divIcon({
  className: 'map-price-marker',
  html: `<div class="price-tag">¥${p.price_monthly}<span>/月</span></div>`,
  iconSize: [80, 32],
  iconAnchor: [40, 32],
})
// 样式: 白底圆角小卡片, 橙色加粗文字, 小阴影
// 选中态: 放大到 1.2x, 橙色底白字, z-index 提升
```

**🟡 P1 — 聚合点 Marker Cluster**

```
缩小到城市/国家级别:
  北京 📍(48)   上海 📍(23)   东京 📍(15)
  蓝色圆点+数字, 数字越大颜色越深

放大到街区级别:
  自动拆分为独立标记
```

实现：`Leaflet.markercluster` 插件，配置 `maxClusterRadius: 80`。

**🟡 P1 — 定位 + "搜此区域"**

右下角悬浮按钮组：
```
┌──────┐
│  🎯   │  定位当前位置 (navigator.geolocation.getCurrentPosition)
├──────┤
│  🔍   │  "搜索此区域" — 取当前 bounds → /map/properties?sw_lat=...&ne_lat=...
├──────┤
│  🏠   │  列表模式 / 地图模式 切换
└──────┘ 
```

监听 `map.on('moveend', () => { if (autoSearch) fetchProperties(bounds) })`。

**🟢 P2 — 房源预览卡（替代原生 popup）**

点击标记 → 地图上弹出 Vue 渲染的预览卡（不用 Leaflet 原生 popup）：
```
┌──────────────────────────┐
│ [封面图 200×120]    ❤️   │
│ 朝阳区精装两居室           │
│ ★★★★☆ 4.5               │
│ 2室1卫 · 85㎡ · 朝阳区    │
│ ¥6,500/月                │
│ [查看详情]    [预约看房]   │
└──────────────────────────┘
```
选择一张房源图片 → `router.push('/property/:id')` 或 `showBookingDialog = true`。

**🟢 P2 — 地铁线路叠加层**

在城市房源密集区，叠加地铁线路 GeoJSON：
- 北京 1/2/10 号线，上海 1/2 号线等
- 标记旁显示最近地铁站名称 + 距离："🚇 劲松站 300m"
- 筛选新增："离地铁站 ≤500m"

数据来源：OpenStreetMap 或各城市公开数据。

**🔵 P3 — 路线规划**

详情页/预览卡：[去这里 🗺️]
- 调用高德 URI `https://uri.amap.com/navigation?to={lng},{lat}`
- 或内置简单路线（Leaflet Routing Machine）
- 显示从当前位置的公交/驾车/步行方案

**🔵 P3 — 街景/全景 (云看房)**

地图右上角切换按钮：`[地图] [卫星] [街景]`
- 街景模式 → 加载腾讯街景 iframe 或 Google Street View
- 让租客在线看房源周边真实环境

**🔵 P3 — 热力图（管理端）**

管理员视角：城市房源密度热力图
- 红=密集(市中心) / 蓝=稀疏(郊区)
- 用 Leaflet.heat 插件
- 帮助房东分析"哪里竞争大/哪里有机会"

#### 12.3.3 技术选型

| 功能 | 推荐方案 | 说明 |
|------|---------|------|
| 地图底图 | Leaflet + OpenStreetMap | 免费无限制，全球覆盖 |
| 聚合点 | leaflet.markercluster | 1.5MB，配置灵活 |
| 热力图 | leaflet.heat | 轻量 |
| 拖拽抽屉 | 手写 CSS transition + touch 事件 | 避免额外依赖 |
| 筛选面板 | Element Plus `el-drawer` | 现成组件 |
| 路线规划 | AMap URI Scheme | 唤起高德App，无需额外 lib |
| 街景 | 腾讯街景 iframe | 国内城市覆盖好 |

| 方案对比 | Leaflet + 插件 | 高德 JS API 2.0 | Mapbox GL JS |
|---------|:---:|:---:|:---:|
| 免费额度 | ✅ 无限制 | ⚠️ 需Key+配额 | ⚠️ 免费50k/月 |
| 海外数据 | ✅ OSM全球 | ❌ 仅中国 | ✅ 全球 |
| 3D/旋转 | ❌ 2D | ❌ 2D | ✅ 3D |
| 自定义样式 | ✅ 完全可控 | ⚠️ 有限 | ✅ Mapbox Studio |
| 文档质量 | ⭐⭐⭐ | ⭐⭐⭐⭐(中文) | ⭐⭐⭐⭐ |

> 建议：**保持 Leaflet 方案**（免费+全球覆盖），渐进增强上述功能。若后续用户量上来且主要面向国内市场，再考虑迁移高德。

#### 12.3.4 实现路线图

| 阶段 | 功能 | 预估工作量 |
|------|------|:---:|
| Phase 1 | 底部抽屉+拖拽 + 筛选面板 | 2-3天 |
| Phase 2 | 价格标签 + Marker Cluster + 定位搜区域 | 1-2天 |
| Phase 3 | 房源预览卡 + 地铁线路 + 路线规划 | 2-3天 |
| Phase 4 | 街景 + 热力图 | 1-2天 |

### 12.4 房东端页面

| 页面 | 行数 | 功能 |
|------|:---:|------|
| CreateProperty.vue | 423 | 发布/编辑房源表单 |
| ManageProperties.vue | 155 | 房源管理列表 |
| PropertyImages.vue | 520 | 拖拽批量上传、排序、设主图 |
| LandlordBookings.vue | 163 | 查看+审批租客预约 |

### 12.5 管理后台

6个页面，路由前缀 `/admin`，权限 `requiresAdmin`。

---

## 十三、数据层

### 13.1 Axios 配置 `services/api.ts`

```typescript
const api = axios.create({
  baseURL: '/api/v1',       // Vite proxy → localhost:8000
  timeout: 10000,
})

// 请求拦截：attach Bearer token from localStorage
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截：
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // 401 时清除 token 并跳转登录（登录页本身除外）
      if (window.location.pathname !== '/login') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    }
    // 提取 detail 字段弹窗
    const detail = error.response?.data?.detail
    if (detail) {
      if (Array.isArray(detail)) detail.forEach(d => ElMessage.error(d.msg))
      else if (typeof detail === 'string') ElMessage.error(detail)
    }
    return Promise.reject(error)
  }
)
```

### 13.2 Pinia Store

**auth store (99行)：**
```typescript
state: { user: User|null, token: string|null, loading: boolean }
getters: { isLoggedIn, isLandlord, isAdmin }
actions: {
  login(data)     → authService.login() → getMe() → setAuth(token, user) → localStorage
  register(data)  → authService.register()
  fetchCurrentUser() → authService.getMe() → update user
  logout()        → clearAuth() → router.push('/login')
  loadFromStorage() → 初始化时从 localStorage 恢复状态
}
```

**property store (135行)：**
```typescript
state: { properties[], searchResults[], currentProperty|null, propertyImages[], loading }
actions: { fetchList, fetchSearch, fetchById, create, update, remove,
           fetchImages, uploadImages, deleteImage, setPrimaryImage }
```

### 13.3 核心类型

```typescript
// Property
{ id, landlord_id, title, description, address, district, price_monthly,
  deposit_amount?, service_fee_rate?, area_sqm, bedrooms, bathrooms,
  property_type: 'apartment'|'house'|'studio'|'shared',
  status: 'available'|'rented'|'maintenance'|'offline',
  latitude?, longitude?, images: PropertyImage[], created_at, updated_at }

// Booking
{ id, tenant_id, property_id, landlord_id,
  status: 'pending'|'approved'|'rejected'|'cancelled'|'completed',
  message?, scheduled_date?, deposit_amount?, service_fee?,
  deposit_status?: 'unpaid'|'paid'|'confirmed',
  payment_transaction_id?, created_at, updated_at }

// BookingCreate（前端发送）
{ property_id: number, message?: string, scheduled_date?: string }

// PaymentCreate
{ booking_id: number, amount: number }
```

---

## 十四、设计规范

### 14.1 颜色

```css
--primary:        #FF6B35;  /* 主色（按钮/链接/高亮）        ████████ */
--primary-light:  #FFF4ED;  /* 浅橙背景                     ████████ */
--primary-dark:   #E85D2C;  /* hover态                      ████████ */
--success:        #67c23a;  /* 可租/成功/已支付              ████████ */
--warning:        #e6a23c;  /* 待确认/待审核                 ████████ */
--danger:         #f56c6c;  /* 价格数字/删除                 ████████ */
--bg:             #f5f6f8;  /* 页面背景                     ████████ */
--bg-white:       #ffffff;  /* 卡片/白色区                  ████████ */
--text-primary:   #303133;  /* 主文字                       ████████ */
--text-secondary: #606266;  /* 次要文字                     ████████ */
--text-muted:     #909399;  /* 辅助/placeholder             ████████ */
--border:         #e4e7ed;  /* 边框                         ████████ */
--border-light:   #ebeef5;  /* 细分隔线                     ████████ */
```

### 14.2 uhomes 品牌主题（`uhomes-theme.css`）🆕

项目 `frontend/src/assets/` 下新增完整设计系统：

```css
/* 品牌色 — uhomes 红 */
--uh-brand-primary: #FF5A5F;
--uh-brand-secondary: #FAD7B7;
--uh-brand-dark-blue: #2C5166;
--uh-brand-purple: #9286BF;

/* 排版 */
--uh-font-family: "Poppins", -apple-system, "system-ui", "Segoe UI", Roboto, sans-serif;
--uh-font-size-body: 14px;
--uh-font-size-hero-heading: 58px;
--uh-font-size-large: 76px;

/* 区块背景 */
--uh-bg-white: #FFFFFF;
--uh-bg-light-purple: #EFEBFA;
--uh-bg-light-green: #F0F7EF;
--uh-bg-dark: #11080D;

/* 按钮 */
--uh-btn-primary-bg: #FF5A5F;
--uh-btn-primary-hover: #E04A4F;

/* 卡片 */
--uh-card-border-radius: 12px;
--uh-card-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
--uh-card-hover-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);

/* 导航 */
--uh-nav-height: 72px;
--uh-layout-max-width: 1280px;
```

> ⚠️ 当前前端仍使用 Element Plus 默认橙色系 `#FF6B35`，品牌统一到 uhomes 红 `#FF5A5F` 待后续迁移。色彩 Token 文件 `uhomes-design-tokens.json` 已就绪。

### 14.3 圆角

| 元素 | 值 |
|------|-----|
| 卡片 `el-card` | 12px (`--radius`) |
| 按钮 `el-button` | 8px (`--radius-sm`) |
| 搜索条 | 28-36px (round) |
| 标签 `el-tag` | 6px |
| 对话框 `el-dialog` | 16px (`--radius-lg`) |

### 14.4 阴影

```css
--shadow-sm: 0 1px 4px rgba(0,0,0,0.04);
--shadow:    0 2px 12px rgba(0,0,0,0.06);
--shadow-lg: 0 4px 24px rgba(0,0,0,0.08);
```

### 14.5 配套标签（PropertyCard 中）

```css
background: #fdf6ec; border: 1px solid #f5dab1; color: #b88230;
border-radius: 20px; font-size: 11px;
```

### 14.6 按钮规范

- 主操作按钮：`type="primary"` 橙色底白字，圆角 `round` 或 8px
- 次要操作：`text` 或 `plain`
- 危险操作：`type="danger"`
- 全部大写字母：`size="large"` 用于主要CTA
- hover: 加深背景色，`transform: translateY(-1px)`
- disabled: `opacity: 0.6; cursor: not-allowed`

### 14.7 表格

- 所有表格使用 `stripe` 属性
- 操作列宽度 160-240px
- 状态列使用 `el-tag` + 映射色
- 空状态使用 `el-empty` + 引导按钮

### 14.8 弹窗

- 预约弹窗：460px 宽
- 报修弹窗：420-450px
- 认证弹窗：400-420px
- 管理员资料弹窗：500px

---

## 十五、后端接口对照

### 15.1 服务模块映射

| 前端 Service | 后端路由 | 方法 | 用途 |
|-------------|---------|:---:|------|
| `auth.ts` | `/auth` | 4 | login, register, wechatLogin, getMe |
| `property.ts` | `/properties` + `/pois` | 10 | CRUD + search + images + POI |
| `booking.ts` | `/bookings` | 5 | create, list, getById, updateStatus, cancel |
| `payment.ts` | `/payments` | 3 | create, get, callback |
| `contract.ts` | `/contracts` | 3 | get, sign, download |
| `user.ts` | `/users` | 2 | getMe, updateMe |
| `chat.ts` | `/chat` | 4 | session CRUD + messages |
| `notification.ts` | `/notifications` | 3 | list, markRead, markAllRead, unreadCount |
| `admin.ts` | `/admin` | 6 | dashboard, users, properties, logs, embeddings, import |
| `map_routes.py` 🆕 | `/map` | 2 | properties (坐标列表), config (key) |
| `geocoding.py` 🆕 | `/geo` | 1 | geocode (地址→经纬度，高德API) |

**总计：11个前端模块 | 43个API端点**

**2026-06-26 新增后端模块：**
| 模块 | 文件 | 说明 |
|------|------|------|
| 地理编码 | `geocoding_service.py` | 高德地理编码：地址→坐标，周边POI搜索 |
| 支付服务 | `payment_service.py` (444行) | 完整押金/租金支付、退款、对账逻辑 |
| 短信 | `sms_service.py` | 阿里云短信（预约提醒、支付通知） |
| 邮件 | `email_service.py` | SMTP 邮件通知 |
| 评价模型 | `models/review.py` | 房源评价（用户+房东回复+评分） |
| 收藏 | `models/saved_search.py` | 用户保存的搜索条件 |
| 广告 | `models/advertisement.py` | 房源推广/置顶广告 |
| 市场 | `models/marketplace.py` (156行) | 二手市场/租房周边交易 |
| 机构 | `models/institute.py` | 合作机构（学校/企业） |
| 新闻 | `models/news.py` | 平台资讯/公告 |

### 15.2 已知问题

| 问题 | 影响 | 临时方案 |
|------|------|---------|
| 后端无 `country` 字段 | 国家筛选无效 | 前端映射到 `district` |
| 后端无 `amenities` | 设施数据为空 | 前端根据类型/地区推断 |
| 后端无 Reviews API | 评价区无数据 | 静态 mock 4条 |
| 后端无 Favorites API | 收藏功能不可用 | 暂用 `list()` 代替 |
| `booking.time_slot` 不存在 | 时间段无法存储 | 拼入 `message` 字段 |
| `LoginRequest.require_identifier` | Pydantic ValueError 序列化崩溃 | 已修复（简化Schema） |

---

## 十六、附录

### 16.1 已修复的后端问题

| 问题 | 文件 | 修复方式 |
|------|------|---------|
| LoginRequest ValueError 导致 500 | `schemas/auth.py` | 移除 model_validator，简化为 `str` 必填字段 |
| _build_error_response JSON崩溃 | `core/logging.py` | 安全提取 dict 的 msg/loc |
| map.py 与 Python 内置冲突 | `routes/map.py → map_routes.py` | 重命名 |

### 16.2 已实现的前端关键修复

| 问题 | 解决方式 |
|------|---------|
| 登录/注册按钮无反应 | 按钮移出 el-form，本地 loading，避免 authStore.loading 卡死 |
| 登录后仍显示登录按钮 | 改回 authStore.login() 更新 Pinia 响应式状态 |
| 通知红标不更新 | DefaultLayout 中 watch(route.path) 重新 fetchUnreadCount |
| 日历可选过去日期 | computed setter + CSS pointer-events + 月份切换判断 |
| 租客/房东侧边栏混在一起 | v-if 完全分离两套菜单 |
| 预约后跳到支付页 | 移除 Step 2/3，直接保存 + 提示 + 跳个人中心 |
| 已支付订单仍显示在预订列表 | 过滤 deposit_status !== 'paid'/'confirmed' |
| 支付中心数字不变 | 改用 contracts.length（已支付合同数）|

### 16.3 最新进展（2026-06-26 main 分支合并）

| 模块 | 状态 | 说明 |
|------|:---:|------|
| 高德地图组件 | ✅ 已实现 | `AmapMap.vue` — 详情页地图，支持 Key 配置降级 |
| 地理编码 API | ✅ 已实现 | `POST /geo/geocode` — 地址→经纬度 |
| 支付服务 | ✅ 已实现 | `payment_service.py` 444行完整逻辑 |
| SMS 短信通知 | ✅ 已实现 | 阿里云短信 SDK |
| Email 邮件通知 | ✅ 已实现 | SMTP 邮件 |
| Review 评价模型 | ✅ 已建表 | 前端待对接 |
| SavedSearch 收藏 | ✅ 已建表 | 前端待对接 |
| Advertisement 广告 | ✅ 已建表 | 前端待对接 |
| uhomes 设计系统 | ✅ Token 已就绪 | 品牌色 `#FF5A5F`，前端待迁移 |

### 16.4 待前端对接

| 后端已有 | 前端需做 |
|---------|---------|
| Review 模型 + API | 详情页评价区接入真实数据，替换 mock |
| SavedSearch 模型 | 搜索页"保存当前搜索"功能 |
| Advertisement 模型 | 首页/搜索页房源置顶推广 |
| SMS 服务 | 预约确认/支付成功短信通知 |
| Email 服务 | 合同签署邮件通知 |
| Geocoding API | 发布房源时自动获取经纬度 |
| uhomes 主题 CSS | 全局替换 Element Plus 橙色为品牌红 #FF5A5F |

---

> **文档结束**  
> 本文档覆盖前端全部 50+ 文件、26 条路由、10 个服务模块、4 个公共组件、2 个 Store、6 个类型文件。  
> 所有数据流、组件树、路由守卫、设计规范均已详述。AI 或开发人员可据此完整复现全部前端功能。

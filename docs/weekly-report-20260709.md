# 项目周报

**项目**: 租房匹配平台  
**周期**: 2026.07.03（周四）— 2026.07.09（周三）  
**本周摘要**: 6 人贡献，合并 5 个 PR，累计 24 次 commit，新增/修改 350+ 文件，净增 ~85,000 行代码

---

## 一、贡献者总览

| 成员 | 角色 | Commits | PR | 主要产出 |
|------|------|:---:|:---:|----------|
| MichaelLee | 项目负责人/全栈 | 6 | —（直接合并） | 多地图引擎、SMS验证码、邮件通知、设计系统、团队基建 |
| lu-sir1219 | 房源管理 | 9 | #18 | 维修系统全栈、房源管理升级、回收站、角色系统、BD/房东数据台 |
| Michael9047 | 消息通知 / 协调 | 7 | #16 #17 | PR 审核合并、CI 修复、房源管理 PR 整合 |
| JiaWu1211 | 支付流程 | 1 | #21 | 预订流程重构（三步表单+协议确认） |
| shen25308 | AI 搜索流 | 1 | #20 | 租房推荐Agent、候选清单、加权对比、FAQ工作流 |
| Riki-1124 | 维修实现 | 1 | #19 | 维修系统前端集成、BD数据台 |

---

## 二、每日进展

### 周四（07.03）

- 无提交记录（前期规划与设计阶段）

### 周五（07.04）— 项目基建

- **MichaelLee** 完成项目工程化搭建：
  - 新增 GitHub 看板自动化 workflow（`project-automation.yml`），Issue/PR 自动关联项目看板
  - 配置分支保护规则与分支命名检查 CI（`branch-name-check.yml`）
  - 补充 163 个 Issue 标签（模块 + 技术栈 + 优先级全覆盖）
  - 创建 `CLAUDE.md` / `AGENTS.md` 协作规范，统一分支命名与 commit 格式
  - 清理废弃文件（`reantal.md`、`uhomes_design_tokens.json`、旧截图等），仓库瘦身 ~1,700 行

### 周六（07.05）

- 无提交记录

### 周日（07.06）— 地图/验证码/通知大版本 + 房源管理启动

- **MichaelLee** 提交本周最大单次 commit `90f54e1`（300+ 文件，~80,000 行）：
  - **多地图引擎架构**：高德 → 抽象为多引擎（高德 / Google Maps / OSM Nominatim），按国家自动路由，`GeocodingService` 完整重构
  - **Google Maps 全覆盖**：前端 `GoogleMap.vue` 组件（191 行）、`MapSearch` 国家筛选、`CreateProperty` 国家选择器，后端 `map_routes.py` 扩展，就差接 API Key
  - **SMS 验证码注册**：`auth.py` 新增 `/register/send-code` + `/register/verify-code` 端点，对接阿里云 dypnsapi 号码认证，`sms_service.py` 完整实现，验证码正常工作中
  - **邮件通知全覆盖**：7 种新通知类型（`contract_signed` / `payment_received` / `booking_confirmed` 等），`notification_service.py` 扩展，支付/合同事件自动触发邮件
  - **多国家房源**：`Property` 新增 `country` 字段，`CountryCode` 枚举覆盖 14 个国家/地区
  - **支付重构**：`Payment.status` 改为 `PaymentStatus` 枚举，新增微信支付字段
  - **设计系统**：`uhomes-design/` 完整设计系统（`tokens/` + `references/` + `SKILL.md` 2473 行），色彩/间距/字体/动画/组件/交互规范全部落地
  - **团队配置**：更新 `CODEOWNERS` 6 人分工、`.github/PULL_REQUEST_TEMPLATE.md`
  - **知识库**：`.qoder/repowiki/` 自动生成完整项目文档（架构/API/前端/部署/测试共 140+ 篇）

- **lu-sir1219** 启动房源管理升级 `d32a0ed`：
  - 公寓分组展示（展开/折起）、批量操作（上架/下架/删除/绑定公寓）
  - 图片上传（发布+批量导入均支持）、高级检索筛选、滚动高亮
  - 修复 11 个 Bug（`room_number` 丢失、状态未定义、字段缺失、缓存不同步等）

### 周一（07.07）— 维修系统全栈 + 房源管理收尾

- **lu-sir1219** 完成维修系统 5 个 PR + 房源升级（全天密集提交）：
  - **PR1** `1c752b3` — 角色系统改造：新增 `maintenance_worker` 角色，激活 `bd_manager`，权限守卫/路由/侧边栏全链路适配
  - **PR2** `0cfaa2b` — 维修系统后端：`RepairRequest` + `RepairWorker` 双表模型，10 个 API 端点，CRUD + 状态流转 + 派单 + 完成记录，4 种新通知类型
  - **PR3** `c56a973` — 维修系统租客端：报修页面对接真实 API，`RepairDetail` 详情页，Pinia store + API 客户端 + 类型定义
  - **PR4** `9da4dca` — 房东/维修师傅管理端：房东数据台（统计卡片+快捷入口）、报修管理（筛选+派单弹窗）、维修师傅管理（创建账号+状态调整）、师傅数据台+工单列表
  - **PR5** `2d58be3` — BD 经理数据台：统计卡片 + 区域分布图表，5 个 PR 全部完成（40+ 文件）
  - **房源管理升级** `d168901` — 12 项刚需：分页 API / 软删除 / 硬删除 / 状态机 / 乐观锁 / 审计日志 / 批量事务 / 回收站（公寓分组+恢复+硬删除+批量）/ 6 个新字段（amenities/available_from/min_stay_months/deposit_type/version/deleted_at）
  - **修复** `2893087` — API 响应提取 `.then(r=>r.data)` 缺失、BD 角色权限、工单列表渲染错误、BD 数据台对接真实 API

- **MichaelLee** CI 修复 `0880a5c`：project-automation workflow 中 `orgs` 路径改为 `users`，适配个人仓库

- **Riki-1124** Git 配置更新 `3b9fcdc`

### 周二（07.08）— Agent 智能推荐 + 预订流程重构 + 集中合并

- **shen25308** PR #20 `9bb1eef` — 租房推荐 Agent 全栈：
  - **后端**：`AgentService` 意图路由（recommend/加购/移除/对比/faq/general），三层检索漏斗（SQL 过滤 → pgvector 语义 → LLM 精选），LLM 不可用时自动降级
  - **候选清单**：`agent_carts` / `agent_cart_items` 双表 + 迁移，购物车增删/持久化
  - **对比引擎** `compare_scoring.py`：确定性加权评分（价格/通勤/空间/评价四维 + 用户优先级权重），接入 POI 通勤距离与真实评价，LLM 只解释不打分
  - **FAQ 工作流**：知识库 + 三层匹配（chips 直答 / LLM 分类 / 弱命中反问）
  - **Embedding**：接入智谱 AI（OpenAI 兼容，1536 维对齐），新房源同步生成 embedding
  - **前端**：推荐管家横条、候选清单抽屉、对比弹窗（优先级切换）、浮动 AI 气泡（可拖动/放大/迷你对话/FAQ chips）、聊天跨页持久化
  - **测试**：pytest 全绿（除 2 个既有 geocoding 遗留），vue-tsc 干净

- **JiaWu1211** PR #21 `f1f96d0` — 预订流程重构：
  - 后端：`rent_type` 枚举（整租/合租）、`min_lease_months` / `deposit_type` 字段、Alembic 迁移 + 数据脚本
  - 前端：全新 `BookingFlow.vue` 三步表单流程
    - **第一步** — 租期选择（`LeaseStep` + `StartDateStep`，日历选择入住日期 + 租期滑块）
    - **第二步** — 个人信息（`PersonalInfoStep`：申请人 `ApplicantForm` + 紧急联系人 `EmergencyForm` + 担保人 `GuarantorForm`）
    - **第三步** — 协议确认（`AgreementStep` + `AgreementDialog`，租房协议阅读 + 电子签名确认）
  - 全局状态管理 `bookingFlow.ts` store（277 行），支持分步回退和数据持久化
  - 22 个文件，净增 3,580+ 行

- **MichaelLee** 集中解决合并冲突：
  - `d28ff9c` — 解决 PR #17 #18 #19 路由注册冲突（router.py 合并 buildings/dashboard/favorites/ml/repairs/repair_workers/upload 全部路由）
  - `21c289d` — 解决 PR #20（Agent）冲突（router.py + config.py + property_service.py + DefaultLayout.vue）
  - `2b94fbf` — 解决 PR #21（预订流程）冲突（models/property.py + schemas/property.py + types/property.ts 字段合并）

- **Michael9047** 审核合并 PR #17（房源管理）→ #19（维修前端）→ #18（房源升级+回收站）→ #20（Agent）→ #21（预订流程），完成 main 分支最终集成

---

## 三、模块进度汇总

| 模块 | 本周进展 | 负责人 | 状态 |
|------|----------|--------|:---:|
| 🗺️ 地图服务 | 多地图引擎架构（高德/Google/OSM），按国家路由，GoogleMap 组件就绪，待接 API Key | MichaelLee | ✅ 基本完成 |
| 📩 消息通知 | 7 种新通知类型，支付/合同事件自动邮件 | Michael9047 / MichaelLee | ✅ 已完成 |
| ✉️ 邮件功能 | 通知事件自动触发邮件，验证码邮件，合同/支付邮件通知全覆盖 | MichaelLee | ✅ 已完成 |
| 📱 SMS 验证码 | 注册验证码发送+校验，对接阿里云 dypnsapi，密码重置流程 | MichaelLee | ✅ 已完成 |
| 🔧 维修系统 | 全栈：后端模型+API+服务层 → 租客端报修 → 房东派单 → 师傅接单+完工 → BD 数据台 | lu-sir1219 / Riki-1124 | ✅ 已完成 |
| 🏠 房源管理 | 回收站、12 项刚需升级（分页/软删除/状态机/乐观锁/审计/批量）、公寓分组、图片上传 | lu-sir1219 | ✅ 已完成 |
| 🤖 智能推荐 Agent | 意图路由+三层检索+候选清单+加权对比+FAQ+浮动AI助手，全栈交付 | shen25308 | ✅ 已完成 |
| 📅 预订流程 | 三步表单重构（租期→个人信息→协议确认），租期类型/押金类型扩展 | JiaWu1211 | ✅ 已完成 |
| 👥 角色系统 | maintenance_worker 新增 + bd_manager 激活，全链路权限适配 | lu-sir1219 | ✅ 已完成 |
| 📊 数据台 | 房东数据台 + 维修师傅数据台 + BD 经理数据台，三个角色运营面板 | lu-sir1219 / Riki-1124 | ✅ 已完成 |
| 🎨 设计系统 | uhomes-design 完整规范（tokens + 组件 + 交互 + 动画 + 布局） | MichaelLee | ✅ 已完成 |
| 🔐 支付系统 | PaymentStatus 枚举重构，微信支付字段扩展 | MichaelLee | ✅ 已完成 |
| 🌍 多国家 | CountryCode 14 个国家/地区，Property.country 字段，前后端全链路 | MichaelLee | ✅ 已完成 |
| ⚙️ CI/CD | 看板自动化、分支命名检查、分支保护规则、PR 模板、Issue 标签体系 | MichaelLee / Michael9047 | ✅ 已完成 |

---

## 四、关键数据

| 指标 | 数值 |
|------|------|
| 本周 Commits | 24 |
| 合并 PR | 5 个（#16 #17 #18 #19 #20 #21） |
| 活跃贡献者 | 6 人 |
| 新增/修改文件 | 350+ |
| 净增代码行 | ~85,000 行 |
| 新建数据表 | agent_carts, agent_cart_items, repair_requests, repair_workers |
| 新建 API 端点 | 30+ |
| 新建前端页面/组件 | 25+ |
| Alembic 迁移 | 8 个 |
| 测试文件 | 3 个新增（test_agent / test_agent_faq / test_compare_scoring） |

---

## 五、下周计划

- [ ] Google Maps API Key 接入，完成地图引擎最后一块拼图
- [ ] 端到端集成测试：预订流程 → 支付 → 合同 → 通知全链路
- [ ] 维修系统与通知系统联调（报修状态变更自动推送）
- [ ] Agent 推荐准确率评估与调优
- [ ] 微信小程序端启动开发
- [ ] 性能压测（pgvector 语义搜索 + LLM 调用链路）
- [ ] 文档补齐：新模块 API 文档、部署文档更新

---

## 六、风险与阻塞

| 风险 | 等级 | 说明 |
|------|:---:|------|
| Google Maps API Key | 🟡 中 | 组件已就绪但未接入 Key，功能不可用，需尽快申请 |
| PR 集中合并冲突 | 🟢 已解决 | 周二集中合并多个 PR 产生大量冲突，已全部解决 |
| 测试覆盖 | 🟡 中 | 新模块（维修/Agent/预订）缺少端到端集成测试 |
| 文档同步 | 🟡 中 | 代码快速迭代，API 文档需同步更新 |

---

*报告生成时间: 2026-07-09 · 数据来源: git log + GitHub PR history*

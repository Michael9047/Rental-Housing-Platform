# 死代码审计报告

> 日期：2026-08-10 | 审计范围：整个项目（backend + frontend）

---

## 概述

4 个并行代理分别审计了路由注册、重复/重叠代码、前端死代码、后端 Service/Celery。共发现 **~70 项死代码/孤儿代码**。

| 类别 | 数量 | 涉及文件 |
|------|------|----------|
| 未注册路由文件 | 7 | 3 注释掉 + 4 从未引用 |
| 完全死 Service | 7 | 零 import 的服务文件 |
| 生产环境死 Service | 1 | 仅测试引用 |
| 死 Schema | 2 | room.py, room_type.py |
| 死 Model 兼容桩 | 1 | room_transfer.py |
| 前端死页面 | 23 | 未在 router 中注册的 .vue |
| 前端死组件 | 10 | 从未被 import 的组件 |
| 前端死 Store | 2 | compare, repair |
| 前端死 Service | 4 | aiSearch, favorite, crystalroof, compare |
| Celery 孤儿任务 | 7 | 从未被触发/调度的 task |
| 旧版重定向 | 2 | 指向已删除或错误页面的路由 |

---

## 1. 后端路由 — 7 个死文件

### 1.1 注释掉但缺少 import（3 个）

这些文件在 `router.py` 中有注释掉的 `include_router`，但 import 块中也未导入它们。即使取消注释也会因 `NameError` 而崩溃。

| 文件 | 端点数 | 注释内容 |
|------|--------|----------|
| `routes/ai_search.py` | 2 | `# api_router.include_router(ai_search.router, ...)` — 且前端 AiSearch.vue 会调 `/ai-search/*` |
| `routes/ml.py` | 6 | `# api_router.include_router(ml.router, ...)` — 租金预估 + 模型训练 |
| `routes/pms.py` | 7 | `# api_router.include_router(pms.router, ...)` — PMS 对接管理 |

### 1.2 完全未引用（4 个）

这些文件在 `router.py` 中没有任何 import 或 include_router 调用，完全不可达。

| 文件 | 端点数 | 说明 |
|------|--------|------|
| `routes/compare.py` | 3 | 房源对比会话 API。前端 `CompareView.vue` 也未路由，全链路死。 |
| `routes/crystalroof.py` | 2 | CrystalRoof 安全评分。前端 service 也是死的。 |
| `routes/images.py` | 4 | 图片上传/删除/设主图 CRUD。注意：前端 `PropertyImages.vue` 直接调 `propertyService` 处理图片，不经过此路由。 |
| `routes/reviews.py` | 8 | 完整的评价系统（CRUD + 聚合统计 + 审核）。**最大的孤儿模块。** |

### 1.3 main.py 内联路由（2 个）

| 路径 | 说明 |
|------|------|
| `GET /api/v1/public/buildings` | 绕过路由系统的公开楼栋列表 |
| `GET /` | 根路径健康检查 |

这两个是刻意设计，非死代码。

---

## 2. 后端 Service — 7 个完全死 + 1 个生产环境死

### 2.1 完全死（零 import）

| 文件 | 说明 |
|------|------|
| `services/dropbox_sign_service.py` | Dropbox Sign 电子签章服务。曾用于第三方合同签署，已被自研签章替代。 |
| `services/stage_classifier.py` | 对话阶段识别器。文件自注"已合并到 AgentService.classify_message()"。 |
| `services/search_state.py` | 基于 Redis 的搜索状态持久化（SearchStateManager + TTL）。所有 `search_state` 引用均为变量名，非模块导入。 |
| `services/room_service.py` | 废弃的 Room CRUD 服务。所有方法抛 `NotImplementedError`。 |
| `services/room_type_service.py` | 废弃的 RoomType CRUD 服务。返回空列表或 `NotImplementedError`。 |
| `services/commute_precompute.py` | 通勤预计算（按 room_id 计算到各大学通勤时间）。关联已删除的 Room 模型。 |
| `services/query_rewriter.py` | LLM 查询改写。`tool_registry.py` 已有内联的 `_query_rewrite` 替代。 |

### 2.2 生产环境死（仅测试引用）

| 文件 | 说明 |
|------|------|
| `services/contract_pdf_service.py` | 旧版 WeasyPrint 合同 PDF 生成。仅在 `tests/test_contract_rendering.py` 中 import。生产代码使用 `contract_pdf_render_service.py`。 |

### 2.3 部分死（使用极少）

| 文件 | 状态 |
|------|------|
| `services/notification_sms_service.py` | 仅在 test 和 tasks 中 import，无路由直接调用 |
| `services/embedding_job_service.py` | 仅在 `services/__init__.py` 中导出，无路由直接 import |

---

## 3. 后端 Schema — 2 个死文件

| 文件 | 说明 |
|------|------|
| `schemas/room.py` | 定义了 `RoomCreate`, `RoomUpdate`, `RoomRead`, `RoomListResponse`, `BatchStatusUpdate`, `BatchDelete`。**全后端零 import。** |
| `schemas/room_type.py` | 定义了 `RoomTypeEnum`, `RoomTypeStatus`, `DepositType`, `RoomTypeBase/Create/Update/Read`。**全后端零 import。** 注意：`DepositType` 枚举在 `unit_type.py` 中有等价的字符串字段。 |

### 保留但需注意

| 文件 | 状态 |
|------|------|
| `schemas/property.py` | 文件自注"兼容占位 — Phase 3 重写后删除"。但 `agent.py`、`property_service.py`、`pms/sync_service.py` 仍在 import。**不能删。** |
| `models/property.py` | 40+ 文件依赖的模型桥接。**不能删。** |
| `models/property_image.py` | 多个 service 依赖。**不能删。** |

---

## 4. 后端 Model 兼容桩

| 文件 | import 数 | 建议 |
|------|-----------|------|
| `models/room_transfer.py` | **0** | ✅ 立即可删 |
| `models/order.py` | 1（`scripts/test_notification_scenarios.py`） | 迁移测试后删除 |
| `models/room_type.py` | 1（`scripts/seed/seed_v2_properties.py`） | 迁移 seed 脚本后删除 |
| `models/room_commute.py` | 1（`services/commute_precompute.py`） | 与 commute_precompute.py 一起删除 |
| `models/_compat.py` | 2（order.py, room_transfer.py） | 上两者删除后即可删 |
| `models/property.py` | **40+** | ❌ 暂不能删 |
| `models/property_image.py` | 多个 service | ❌ 暂不能删 |

---

## 5. Celery 孤儿任务 — 7 个

### 5.1 零 .delay() 调用 + 零 beat_schedule（4 个）

| 任务 | 文件 | 说明 |
|------|------|------|
| `send_payment_result_message` | `tasks/payment_tasks.py:234` | 支付结果微信模板消息——从未发送 |
| `send_booking_reminder_message` | `tasks/notification_tasks.py:117` | 看房提醒微信消息——从未发送 |
| `sync_pending_payments` | `tasks/payment_tasks.py:119` | 定期同步待处理支付——代码注释说"should be scheduled every 5 min via Celery Beat"但从未配置 |
| `close_expired_payments` | `tasks/payment_tasks.py:160` | 关闭超时支付——注释说"should be scheduled via Celery Beat"但从未配置 |

### 5.2 缺少 beat_schedule（1 个）

| 任务 | 文件 | 说明 |
|------|------|------|
| `train_rent_model` | `tasks/ml_tasks.py:20` | 每天凌晨 2:07 训练 XGBoost 租金模型——文件注释写了 crontab 配置但从没加到 celery_app.py |

### 5.3 仅内部/回填触发（2 个）

| 任务 | 文件 | 说明 |
|------|------|------|
| `backfill_all_map_pois` | `tasks/poi_tasks.py:229` | 批量补填地图 POI——无外部 .delay() 调用 |
| `backfill_safety_scores` | `tasks/poi_tasks.py:283` | 批量补填安全评分——无外部 .delay() 调用 |

---

## 6. 前端死页面 — 23 个

### 6.1 旧版 booking 流程（1+12=13 个）

| 文件 | 说明 |
|------|------|
| `views/BookingFlow.vue` | 旧版 5 步预约流程（StartDate→Lease→PersonalInfo→Agreement→Payment） |
| `components/booking/StartDateStep.vue` | 仅被 BookingFlow.vue import |
| `components/booking/LeaseStep.vue` | 仅被 BookingFlow.vue import |
| `components/booking/PersonalInfoStep.vue` | 仅被 BookingFlow.vue import |
| `components/booking/AgreementStep.vue` | 仅被 BookingFlow.vue import |
| `components/booking/ApplicantForm.vue` | 仅被 BookingFlow.vue import |
| `components/booking/EmergencyForm.vue` | 仅被 BookingFlow.vue import |
| `components/booking/GuarantorForm.vue` | 仅被 BookingFlow.vue import |
| `components/booking/AgreementDialog.vue` | 仅被 BookingFlow.vue import |
| `components/booking/PolicyDialog.vue` | 仅被 BookingFlow.vue import |
| `components/booking/SignaturePad.vue` | 仅被 BookingFlow.vue import |
| `components/booking/AddressSelector.vue` | 仅被 BookingFlow.vue import |
| `components/booking/BookingFlowLayout.vue` | 仅被 BookingFlow.vue import |
| `stores/bookingFlow.ts` | 仅被上述死组件 import |

> 新流程使用 `views/booking/` 下的 MoveInDate→LeaseTerm→PersonalInfo→EmergencyContact→BookingReview→ContractPlaceholder 6 步。

### 6.2 AI 相关页面（4 个）

| 文件 | 说明 |
|------|------|
| `views/AgentView.vue` | "Rental Recommendation Agent" 全屏页——未路由 |
| `views/ChatView.vue` | "AI Rental Assistant EstateWise Engine" 聊天页——未路由 |
| `views/SmartRentView.vue` | "Smart Rent" AI 聊天页——未路由 |
| `views/CompareView.vue` | 房源对比页——未路由 + 后端 route 也是死的 |

### 6.3 旧版替代页面（2 个）

| 文件 | 说明 |
|------|------|
| `views/PropertyDetail.vue` | 旧版房源详情——已被 `BuildingDetail.vue` + `BuildingRedirect.vue` 替代 |
| `views/SearchSimple.vue` | 简化搜索页——未路由 |

### 6.4 Admin 子页面（6 个）

这些文件存在但 router 中 `/admin` 只指向 `AdminWorkspace.vue`，以下子页面从未被路由到：

| 文件 | 说明 |
|------|------|
| `views/admin/AdminDashboard.vue` | 数据看板 |
| `views/admin/AdminEmbeddings.vue` | 向量嵌入管理 |
| `views/admin/AdminImport.vue` | 数据导入 |
| `views/admin/AdminProperties.vue` | 楼栋审核 |
| `views/admin/EscalatedRepairs.vue` | 升级工单 |
| `views/admin/LandlordWorkersStatus.vue` | BM/维修工状态 |

### 6.5 其他未路由页面（5 个）

| 文件 | 说明 |
|------|------|
| `views/AdminWorkspace.vue` | 根级副本——router 使用的是 `admin/AdminWorkspace.vue` |
| `views/MapSearch.vue` | 地图搜索页 |
| `views/WeChatCallback.vue` | 微信 OAuth 回调 |
| `views/ContractTemplateManager.vue` | 合同模板管理 |
| `views/ReviewForm.vue` | 评价表单 |
| `views/RoomTransferLog.vue` | 房间调拨日志 |
| `views/OrderManagement.vue` | 订单管理 |
| `views/bd-manager/BdDashboard.vue` | BD Manager 看板 |
| `views/landlord/LandlordDashboard.vue` | BM 看板（router 用 AdminWorkspace 代替） |
| `views/policies/PolicyDocument.vue` | 通用政策文档页（booking 流程中改用 PolicyDialog 组件） |

### 6.6 旧版重定向（2 个）

| 路由 | 重定向到 | 问题 |
|------|----------|------|
| `/property/:id` | `/building/:id` | 旧版兼容，可保留 |
| `/booking/:id/move-in-date` | `property-detail` | **目标错误**——应指向新 booking 流程而非房源详情 |

---

## 7. 前端死组件 — 10 个

| 文件 | 说明 |
|------|------|
| `components/AmapMap.vue` | 高德地图组件——`Search.vue` 直接调 `loadGoogleMaps()`，不通过此组件 |
| `components/GoogleMap.vue` | Google Maps 封装——`Search.vue` 内联调用 |
| `components/CommuteRoute.vue` | 通勤路线展示——未 import |
| `components/RentalRulesCard.vue` | 租房规则卡片——未 import |
| `components/ReviewCard.vue` | 评价卡片——仅被死 `ReviewList.vue` import |
| `components/ReviewList.vue` | 评价列表——未 import |
| `components/MiniPropertyCard.vue` | 紧凑房源卡片——全部用 `PropertyCard.vue` |
| `components/RoomTypeCard.vue` | 户型卡片——未 import |
| `components/AssistantBubble.vue` | AI 悬浮气泡——仅在代码注释中被提及 |
| `components/SmartSearch.vue` | 智能搜索框——未 import |

> **注意**：`SearchAgentPanel.vue` 被 `Search.vue` 通过 `defineAsyncComponent` 动态 import，**不是死代码**。

---

## 8. 前端死 Store — 2 个

| 文件 | 说明 |
|------|------|
| `stores/compare.ts` | 对比会话状态——从未被 import。其依赖的 `compareService` 也因此传递性死亡。 |
| `stores/repair.ts` | 维修工单状态——从未被 import。所有维修页面直接调 `repairService`/`workerService`。 |

---

## 9. 前端死 Service — 4 个

| 文件 | 说明 |
|------|------|
| `services/chat.ts` | 聊天 API——仅被死 `ChatView.vue` import |
| `services/compare.ts` | 对比 API——仅被死 `stores/compare.ts` import。后端 route 也是死的。 |
| `services/aiSearch.ts` | AI 搜索 API——从未被 import。`AiSearch.vue`（已路由）直接调 `agentService`。 |
| `services/favorite.ts` | 收藏 API——从未被 import。收藏功能似乎从未接线。 |
| `services/crystalroof.ts` | CrystalRoof 评分——从未被 import。后端 route 也是死的。 |

---

## 10. AI 双版本分析

用户提到的"AI 两版"具体情况：

### 活跃版本（新）
- **路由**: `routes/agent.py`（已注册，15 个端点）
- **Service 层**: `services/agentic/` 完整多 Agent 架构
- **前端**: `SearchAgentPanel.vue`（Search.vue 中动态 import）、`stores/agentChat.ts`、`services/agent.ts`
- **模型**: `agent_session_states`, `agent_user_memories`, `agent_search_runs/candidates`, `agent_carts/items`

### 遗留版本（旧）
- **路由**: `routes/chat.py`（**已注册**但无前端调用）、`routes/compare.py`（未注册）
- **前端**: `ChatView.vue`（未路由）、`AgentView.vue`（未路由）、`SmartRentView.vue`（未路由）、`services/chat.ts`（死）、`services/compare.ts`（死）、`stores/compare.ts`（死）
- **组件**: `AssistantBubble.vue`（死）、`SmartSearch.vue`（死）

### 判定
`chat.py` 路由虽然注册了，但前端 `ChatView.vue` 未路由 + `chat.ts` service 死，实际无人调用。`agent.py` 是唯一活跃的 AI 入口。**可以安全删除**：
- 前端：`ChatView.vue`, `AgentView.vue`, `SmartRentView.vue`, `CompareView.vue`, `services/chat.ts`, `services/compare.ts`, `services/aiSearch.ts`, `stores/compare.ts`, `components/AssistantBubble.vue`, `components/SmartSearch.vue`
- 后端：`routes/compare.py`, `routes/ai_search.py`, `routes/ml.py`（需确认是否要保留租金预估功能）
- 后端 Service：`services/comparison_service.py`, `services/comparison_session_service.py`, `services/comparison_data.py`, `services/stage_classifier.py`, `services/search_state.py`, `services/query_rewriter.py`

---

## 11. 清理优先级建议

### P0 — 立即可删（零依赖，纯死代码）

**后端**：
- `routes/compare.py`, `routes/images.py`, `routes/reviews.py`, `routes/crystalroof.py`（4 个未注册路由）
- `services/room_service.py`, `services/room_type_service.py`, `services/commute_precompute.py`（3 个废弃服务）
- `services/stage_classifier.py`, `services/search_state.py`, `services/query_rewriter.py`（3 个已替代服务）
- `services/dropbox_sign_service.py`（1 个废弃集成）
- `schemas/room.py`, `schemas/room_type.py`（2 个死 Schema）
- `models/room_transfer.py`（1 个死模型桩）

**前端**：
- `views/BookingFlow.vue` + `components/booking/*.vue`（13 个旧 booking 流程文件）
- `stores/bookingFlow.ts`（旧 booking store）
- `views/ChatView.vue`, `views/AgentView.vue`, `views/SmartRentView.vue`, `views/CompareView.vue`（4 个未路由 AI 页面）
- `services/chat.ts`, `services/compare.ts`, `services/aiSearch.ts`, `services/favorite.ts`, `services/crystalroof.ts`（5 个死 service）
- `stores/compare.ts`, `stores/repair.ts`（2 个死 store）
- `components/AmapMap.vue`, `components/GoogleMap.vue`, `components/CommuteRoute.vue`, `components/RentalRulesCard.vue`, `components/ReviewCard.vue`, `components/ReviewList.vue`, `components/MiniPropertyCard.vue`, `components/RoomTypeCard.vue`, `components/AssistantBubble.vue`, `components/SmartSearch.vue`（10 个死组件）

### P1 — 需确认后处理

- `routes/ai_search.py`, `routes/ml.py`, `routes/pms.py` — 注释掉的 3 个路由：是打算后续启用还是彻底放弃？
- `services/contract_pdf_service.py` — 旧 PDF 服务：如果 `test_contract_rendering.py` 仍需要，移入 test fixtures
- `models/order.py`, `models/room_type.py`, `models/room_commute.py` — 各 1 个 consumer，迁移后删除

### P2 — 功能缺口（应启用而非删除）

- **Celery Beat 配置缺失**：`sync_pending_payments`, `close_expired_payments`, `train_rent_model` 三个任务需要配置 beat_schedule
- **支付通知不工作**：`send_payment_result_message` 从未被触发——支付成功/失败后用户收不到微信模板消息
- **看房提醒不工作**：`send_booking_reminder_message` 从未被触发

### P3 — 不能删但应标记

- `models/property.py`（40+ consumer）— 添加 `# TODO: Phase 3 迁移后删除` 注释
- `schemas/property.py`（agent 依赖）— 同上
- `models/property_image.py`（多 service 依赖）— 同上

---

## 12. 统计数据

| 维度 | 总数 | 死代码 | 占比 |
|------|------|--------|------|
| 后端路由文件 | 36 | 7 | 19.4% |
| 后端 Service | ~60 | 7 完全死 + 1 生产死 | ~13% |
| 后端 Schema | ~30 | 2 | 6.7% |
| 后端 Model | ~35 | 4（含兼容桩） | 11.4% |
| Celery 任务 | ~25 | 7 孤儿 | 28% |
| 前端页面 | 75 | 23 | 30.7% |
| 前端组件 | 31 | 10 | 32.3% |
| 前端 Store | 9 | 2 | 22.2% |
| 前端 Service | 31 | 5 | 16.1% |

**全项目死代码率约 20-30%。** 主要集中在三个簇：旧 booking 流程、未接线 AI 页面、废弃的 Room 三层架构残留。

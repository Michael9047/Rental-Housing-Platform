# 公寓与户型生命周期统一 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 统一新建公寓入口，实现公寓与户型安全的上下架、回收站和永久删除流程。

**Architecture:** 使用独立 `BuildingCreateDialog` 统一创建体验；生命周期状态由后端服务集中管理。公寓下架通过查询层父级遮蔽户型，不改写子状态；删除与下架严格分离，所有新预订入口执行服务端可售校验。

**Tech Stack:** Vue 3、TypeScript、Element Plus、FastAPI、SQLAlchemy、Alembic、PostgreSQL、Vitest、pytest

---

### Task 1：扩展生命周期数据模型

**Files:**
- Modify: `backend/app/models/institute.py`
- Modify: `backend/app/models/unit_type.py`
- Create: `backend/alembic/versions/<revision>_add_offline_lifecycle_statuses.py`
- Test: `backend/tests/test_listing_lifecycle.py`

**Steps:**

1. 编写失败测试，断言 `InstituteStatus.offline` 和 `UnitTypeStatus.offline` 存在。
2. 运行 `backend/.venv/Scripts/python.exe -m pytest -s -p no:cacheprovider tests/test_listing_lifecycle.py -q`，确认失败。
3. 添加两个枚举值并生成 PostgreSQL 枚举迁移；迁移必须同时支持升级和回滚。
4. 执行 `alembic upgrade head`，再运行测试。
5. 提交：`feat(property): 增加公寓与户型下架状态`。

### Task 2：建立统一生命周期服务

**Files:**
- Create: `backend/app/services/listing_lifecycle_service.py`
- Modify: `backend/app/services/property_service.py`
- Test: `backend/tests/test_listing_lifecycle.py`

**Steps:**

1. 为公寓/户型上架校验、下架、重新上架和删除资格编写失败测试。
2. 实现 `validate_building_publishable()` 与 `validate_unit_type_publishable()`，返回结构化缺失字段列表。
3. 实现 `offline_building()`、`publish_building()`、`offline_unit_type()`、`publish_unit_type()`；公寓操作不得改写子户型状态。
4. 实现 `has_business_history()`，检查 Booking、Payment、Contract、BookingRoomAssignment 等关联。
5. 所有状态变化写审计日志并刷新搜索缓存版本。
6. 运行专项测试并提交：`feat(property): 统一房源生命周期服务`。

### Task 3：拆分下架与删除 API

**Files:**
- Modify: `backend/app/api/v1/routes/buildings.py`
- Modify: `backend/app/api/v1/routes/unit_types.py`
- Modify: `backend/app/schemas/institute.py`
- Modify: `backend/app/schemas/unit_type.py`
- Test: `backend/tests/test_listing_lifecycle_api.py`

**Steps:**

1. 编写接口权限、状态转换、缺失字段和业务历史冲突测试。
2. 新增 `POST /buildings/{id}/offline`、`POST /buildings/{id}/publish`。
3. 新增 `POST /unit-types/{id}/offline`、`POST /unit-types/{id}/publish`。
4. 保留 `DELETE` 作为进入回收站，但业务历史存在时返回 `409` 和“请改用下架”。
5. 增加批量上下架接口，返回 `success/failed/errors`。
6. 运行测试并提交：`feat(api): 增加公寓与户型上下架接口`。

### Task 4：修复回收站级联恢复语义

**Files:**
- Create: `backend/app/models/listing_deletion.py`
- Create: `backend/alembic/versions/<revision>_track_listing_deletion_batches.py`
- Modify: `backend/app/api/v1/routes/buildings.py`
- Modify: `backend/app/services/listing_lifecycle_service.py`
- Test: `backend/tests/test_listing_recycle_bin.py`

**Steps:**

1. 编写测试：公寓删除前已删除的户型，在恢复公寓时不得被恢复。
2. 添加删除批次记录，保存公寓删除时实际级联的户型 ID。
3. 恢复公寓时只恢复同批次户型，并恢复其删除前状态。
4. 永久删除要求已进入回收站 30 天且无业务历史；否则返回 `409`。
5. 运行测试并提交：`fix(property): 修正公寓回收站级联恢复规则`。

### Task 5：统一搜索与新预订可售校验

**Files:**
- Modify: `backend/app/services/property_service.py`
- Modify: `backend/app/services/booking_availability_service.py`
- Modify: `backend/app/services/payment_service.py`
- Modify: `backend/app/api/v1/routes/buildings.py`
- Modify: `backend/app/api/v1/routes/search_suggestions.py`
- Modify: `backend/app/api/v1/routes/agent.py`
- Test: `backend/tests/test_listing_visibility.py`

**Steps:**

1. 编写矩阵测试：父公寓状态 × 户型状态 × 删除状态 × 库存。
2. 抽取唯一 `is_listable` 查询条件，避免各搜索接口重复且不一致。
3. 所有搜索与租客详情仅返回有效可售户型。
4. 日期校验、创建订单和创建支付时再次检查状态；已有订单后续动作不使用此拦截。
5. 运行搜索、预订和支付回归测试并提交：`fix(search): 统一房源上架可见性校验`。

### Task 6：抽取统一新建公寓组件

**Files:**
- Create: `frontend/src/components/building/BuildingCreateDialog.vue`
- Create: `frontend/src/components/building/__tests__/BuildingCreateDialog.test.ts`
- Modify: `frontend/src/views/ManageProperties.vue`
- Modify: `frontend/src/views/BuildingList.vue`
- Modify: `frontend/src/views/CreateProperty.vue`
- Modify: `frontend/src/views/publish/BatchImport.vue`

**Steps:**

1. 编写组件测试，覆盖地址回填、地图坐标、图片下限、提交载荷和 `created` 事件。
2. 将户型管理页现有创建表单、地图逻辑和设施选项迁入组件。
3. 删除“测试赋值”调试按钮。
4. 四个入口分别接入组件；创建后执行各自刷新或自动选中逻辑。
5. 公寓管理保留独立编辑弹窗，不与创建组件混用。
6. 运行 Vitest 和 SFC 编译，提交：`refactor(frontend): 统一新建公寓入口`。

### Task 7：实现 BM 上下架交互

**Files:**
- Modify: `frontend/src/services/building.ts`
- Modify: `frontend/src/services/property.ts`
- Modify: `frontend/src/views/BuildingList.vue`
- Modify: `frontend/src/views/ManageProperties.vue`
- Modify: `frontend/src/views/UnitTypeList.vue`
- Create: `frontend/src/utils/listingStatus.ts`
- Test: `frontend/src/__tests__/listingStatus.test.ts`

**Steps:**

1. 编写状态标签、允许操作和父级遮蔽提示测试。
2. 公寓列表提供“下架/重新上架”，删除放入更多菜单。
3. 户型卡片提供“下架/重新上架”，并显示“公寓已下架，前台不可见”。
4. 上架失败时展示后端缺失字段并提供“前往编辑”。
5. 有业务历史时隐藏永久删除，删除冲突提示改用下架。
6. 运行专项测试并提交：`feat(frontend): 增加公寓与户型上下架操作`。

### Task 8：补齐上传数据和库存展示

**Files:**
- Modify: `frontend/src/views/CreateProperty.vue`
- Modify: `backend/app/schemas/unit_type.py`
- Modify: `backend/app/services/property_service.py`
- Modify: `frontend/src/views/ManageProperties.vue`
- Test: `backend/tests/test_unit_type_publish_validation.py`
- Test: `frontend/src/__tests__/unitTypePayload.test.ts`

**Steps:**

1. 编写测试确保 `property_type` 必须保存，阻止再次产生类型为空的户型。
2. 校验库存满足 `0 <= available_count <= total_count`。
3. 将“已租”展示改为订单/房号库存的权威聚合结果，不再仅使用 `total_count - available_count`。
4. 对历史空类型数据提供后台补全提示，不自动按名称猜测。
5. 运行测试并提交：`fix(property): 补齐户型发布字段与库存展示`。

### Task 9：全链路验收

**Files:**
- Modify: `docs/` 中相关操作说明
- Test: existing backend and frontend suites

**Steps:**

1. 验证创建公寓的四个入口载荷一致。
2. 验证单独下架户型、公寓父级下架和重新上架。
3. 验证已有订单 #1 在下架期间仍可查看合同和租客信息。
4. 验证下架对象无法搜索、无法新建订单、无法创建支付。
5. 验证有订单对象不可删除，无订单对象可进入回收站并正确恢复。
6. 运行 `git diff --check`、后端专项 pytest、前端 Vitest 和构建；记录项目既有构建错误与本次新增错误的边界。
7. 提交：`test(property): 完成房源生命周期全链路验收`。

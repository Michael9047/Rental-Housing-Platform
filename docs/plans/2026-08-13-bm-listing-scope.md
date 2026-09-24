# BM 房源权限隔离 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让公寓成为 BM 归属的唯一数据源，并确保所有户型管理读写接口只访问当前 BM 可管理公寓下的数据。

**Architecture:** `institutes.bm_id` 保存显式 BM 归属，`unit_types.institute_id` 继承权限，不向户型增加 `bm_id`。管理员可访问全部；普通 BM 仅访问 `bm_id == user.id`，迁移期间兼容尚未分配且由本人创建的数据。公开搜索和租客详情接口继续使用独立公开路由。

**Tech Stack:** FastAPI、SQLAlchemy AsyncSession、Alembic、PostgreSQL、pytest

---

### Task 1: 为户型服务增加公寓范围过滤

**Files:**
- Modify: `backend/app/services/unit_type_service.py`
- Modify: `backend/app/api/v1/routes/unit_types.py`
- Test: `backend/tests/test_unit_type_bm_scope.py`

**Steps:**
1. 编写测试，证明 bm1 只能列出自己公寓下的户型，管理员可列出全部。
2. 让管理列表和回收站列表接收当前用户并关联 `Institute` 使用 `managed_institute_filter`。
3. 为创建、编辑、恢复和复制补充 `can_manage_institute` 校验。
4. 运行目标测试并确认越权请求返回 403。

### Task 2: 统一公寓管理范围和默认归属

**Files:**
- Modify: `backend/app/api/v1/routes/buildings.py`
- Test: `backend/tests/test_building_bm_scope.py`

**Steps:**
1. 将公寓管理列表从 `created_by` 过滤切换到 `managed_institute_filter`。
2. 普通 BM 新建公寓时强制 `bm_id=current_user.id`；管理员保留显式分配能力。
3. 对管理端编辑等写接口复用 `can_manage_institute`。
4. 运行公寓权限测试。

### Task 3: 回填历史公寓 BM

**Files:**
- Create: `backend/alembic/versions/20260813_0046_backfill_institute_bm.py`

**Steps:**
1. 对 `bm_id IS NULL` 且创建者角色为 `landlord` 的公寓回填 `created_by`。
2. 管理员创建或无法识别创建者的公寓保持未分配。
3. 升级本地数据库并核对 bm1 的公寓、户型数量。

### Task 4: 验证完整权限链

**Files:**
- Test: `backend/tests/test_unit_type_bm_scope.py`
- Test: `backend/tests/test_building_bm_scope.py`

**Steps:**
1. 运行新增测试和生命周期回归测试。
2. 用 bm1 与另一 BM 的访问令牌分别调用管理列表接口。
3. 确认 bm1 返回 2 个公寓、2 个户型，另一 BM 无法编辑或复制 bm1 户型。
4. 运行 `git diff --check`。

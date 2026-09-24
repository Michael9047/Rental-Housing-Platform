# 生产上线热修复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不扩大重构范围的前提下，消除今晚生产上线的安全、构建、部署和文件持久化阻断项。

**Architecture:** 保持现有 FastAPI + Vue 3 + Docker Compose 架构。后端权限统一复用楼栋管理范围判断；前端仅修复契约漂移与失效测试；部署使用同一不可变镜像标签，并让后端和 Celery 共享持久化文件卷。

**Tech Stack:** FastAPI、SQLAlchemy async、pytest、Vue 3、TypeScript、Vitest、Docker Compose、GitHub Actions。

---

### Task 1: 短信验证码日志脱敏

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/api/v1/routes/auth.py`
- Test: `backend/tests/test_auth_security.py`

1. 先增加日志回归测试，断言验证码和完整手机号不出现在日志中。
2. 运行目标测试，确认旧实现失败。
3. 删除验证码、正确值和输入值日志字段，手机号统一脱敏。
4. 运行目标测试和认证测试。

### Task 2: 租客资源级权限

**Files:**
- Modify: `backend/app/api/v1/routes/tenants.py`
- Test: `backend/tests/test_tenant_management.py`

1. 增加未认证、跨楼栋房东、合法管理者、管理员测试。
2. 提取按当前用户管理范围查询租客的辅助语句。
3. GET/PATCH/DELETE 全部通过该语句加载目标租客；无权访问统一返回 404。
4. 运行租客管理与相关订单测试。

### Task 3: 前端绿色主干

**Files:**
- Modify: 仅限 `npm run build` 报错涉及的页面、服务与类型文件。
- Test: 失败的 Vitest 测试文件。

1. 运行 `npm run build` 并逐项修复真实契约漂移。
2. 运行失败测试；实现错误修实现，过期结构断言更新测试，日期测试冻结时间。
3. 运行完整 `npm run build` 和 `npm test`，要求退出码均为 0。

### Task 4: 不可变镜像部署

**Files:**
- Modify: `.github/workflows/deploy.yml`
- Modify: `docker-compose.prod.yml`

1. Compose 镜像统一引用 GHCR 和 `IMAGE_TAG`。
2. 部署脚本把本次提交标签写入服务器部署环境。
3. backend、worker、beat 使用相同后端标签。
4. 运行 `docker compose -f docker-compose.prod.yml config` 验证展开配置。

### Task 5: 私有文件持久化

**Files:**
- Modify: `docker-compose.prod.yml`
- Modify: `.gitignore`

1. 为 `/app/uploads` 和 `/app/private_objects` 增加命名卷。
2. Celery 任务挂载需要访问的共享卷。
3. 忽略运行时私有对象和 Vite 输出。
4. 验证 Compose 配置，并在测试部署中执行文件创建、容器重建、文件读取检查。

### Task 6: 上线门禁

1. 后端执行完整 pytest 和空库 Alembic upgrade。
2. 前端执行 build 和完整测试。
3. 执行 `git diff --check`、Compose config 和镜像构建。
4. 冒烟验证登录、房源、租客越权、预约、支付测试、合同文件和健康检查。
5. 任一阻断检查失败则停止正式发布。

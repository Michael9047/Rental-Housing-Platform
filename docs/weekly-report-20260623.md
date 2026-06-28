# 后端开发周报

**项目**: 租房匹配系统  
**负责人**: 后端组  
**周期**: 2026.06.17 - 2026.06.23  

---

## 周一 — 项目初始化与框架搭建

- 选定技术栈：Python FastAPI + SQLAlchemy 2.0 + PostgreSQL 16 + Redis + Celery
- 初始化项目目录结构（`app/api`、`app/models`、`app/schemas`、`app/services`、`app/core`）
- 配置 Alembic 数据库迁移工具，编写初始迁移脚本
- 搭建 FastAPI 应用骨架（CORS、异常处理、日志中间件）
- 编写 `requirements.txt`，确定核心依赖版本

## 周二 — 用户系统 & 房源核心模型

- 设计并创建 **users 表**（用户名、密码哈希、手机号、微信 openid、角色枚举 tenant/landlord/admin）
- 设计并创建 **properties 表**（标题、描述、地址、区域、月租、面积、户型、经纬度、押金、服务费率、pgvector 向量字段）
- 完成 User / Property 的 Pydantic Schema 定义
- 实现 JWT 认证（注册、登录、token 刷新）
- 实现 Property CRUD 接口（增删改查、按区域/状态筛选）

## 周三 — 图片上传 & 预约看房 & 通知系统

- 创建 **property_images 表**（文件名、MIME 类型、大小、排序、主图标记）
- 实现房源图片上传与静态文件服务
- 创建 **bookings 表**（租客/房东/房源关联、预约状态、留言、看房日期）
- 实现预约看房完整流程（创建 → 房东审批/拒绝 → 取消）
- 创建 **notifications 表**（通知类型枚举、已读状态）
- 实现预约状态变更自动推送通知

## 周四 — 即时通讯 & 向量搜索 & 数据导入 & 管理后台

- 创建 **chat_sessions + chat_messages 表**（会话管理、多轮对话、消息角色）
- 实现 Chat Service（LLM 对话 + SSE 流式响应）
- 接入 pgvector，实现房源语义搜索（`text-embedding-3-small` 生成向量）
- 创建 **embedding_jobs 表**，Celery 异步任务批量生成房源向量
- 创建 **data_imports 表**，支持 CSV/Excel/API 批量导入房源
- 实现 Admin 管理后台接口（用户管理、房源审核、数据统计）
- 实现微信小程序登录对接（openid 获取）

## 周五 — 周边设施 & 地理编码 & 安全加固 & 测试

- 创建 **property_pois 表**，实现房源周边设施（交通、餐饮、教育等）自动生成
- 实现地理编码服务（地址 → 经纬度转换）
- 创建 **audit_logs 表**，实现操作审计日志
- 接入 Redis 限流中间件、Prometheus 监控埋点
- 编写 pytest 单元测试（auth、users、properties、bookings、chat、notifications 等 15 个测试文件）
- Docker Compose 部署配置完善（FastAPI + PostgreSQL + Redis + Celery + Nginx）

---

## 已完成模块汇总

| 模块 | 数据表 | API | Service | 异步任务 |
|------|:---:|:---:|:---:|:---:|
| 用户认证 | users | ✅ | ✅ | - |
| 房源管理 | properties | ✅ | ✅ | - |
| 房源图片 | property_images | ✅ | ✅ | - |
| 预约看房 | bookings | ✅ | ✅ | - |
| 通知推送 | notifications | ✅ | ✅ | - |
| 即时通讯 | chat_sessions / chat_messages | ✅ | ✅ | - |
| 语义搜索 | pgvector embedding | ✅ | ✅ | ✅ |
| 数据导入 | data_imports | ✅ | ✅ | ✅ |
| 管理后台 | - | ✅ | ✅ | - |
| 微信登录 | - | ✅ | ✅ | - |
| 周边设施 | property_pois | ✅ | ✅ | - |
| 地理编码 | - | ✅ | ✅ | - |
| 审计日志 | audit_logs | ✅ | ✅ | - |
| 安全/监控 | - | - | ✅ | - |

**技术栈**: FastAPI + SQLAlchemy 2.0（异步） + PostgreSQL 16 + pgvector + Redis + Celery + Docker  
**数据库迁移**: Alembic 共 8 次迁移，14 张表  
**测试**: 15 个 pytest 测试文件  

---

## 下周计划

- 完善单元测试覆盖率
- 前后端接口联调
- 性能优化与压测

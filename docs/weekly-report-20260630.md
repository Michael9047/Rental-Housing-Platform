# 后端开发周报

**项目**: 租房匹配系统  
**负责人**: 后端组  
**周期**: 2026.06.24 - 2026.06.30  

---

## 周一（06.24）— 通知系统扩展 + 机构模型

- 扩展通知类型枚举，新增 `contract_signed`、`payment_received`、`review_reply` 等类型
- 设计并创建 **institutes 表**（公寓管理机构：名称、地址、联系方式、API 配置）
- BD 经理角色关联机构录入流程
- 扩展 `properties` 表，新增 `institute_id` 外键关联

## 周二（06.25）— 评论 + 收藏 + 广告模型

- 创建 **reviews 表**（房源评价：用户评价 + 房东回复 + 评分 1-5）
- 创建 **saved_searches 表**（用户保存的搜索条件）
- 创建 **advertisements 表** + **ad_impressions 表**（房源推广置顶广告 + 曝光统计）
- 更新 Pydantic Schema，前后端接口联调数据字段对齐

## 周三（06.26）— 机构模型收尾 + 前端重构启动

- 完善 institutes 表的管理员审核流程（`reviewed_by` 字段）
- 创建 Alembic 迁移 0010：`20260626_0010_institutes_v15_v2.py`
- 前端启动完整 UI 重构：租客端 + 公寓管理员后台 + 预约支付流程

## 周四（06.27）— 前端 UI 重构推进

- 租客端页面重构：房源详情、预约流程、个人中心 7 Tab
- 公寓管理员后台 8 Tab 运营工作台
- 支付流程集成：押金支付 → 电子合同签署
- 地图找房页面：Leaflet + 视口框选 + 手动聚合簇

## 周五（06.28）— 合并迁移 + 地图找房收尾

- 合并 UI 重构分支到 main：多头迁移整合（`5ac4aa5f38f4_merge_migration_heads_after_ui_branch_`）
- 地图找房功能完成：`feat(map): 实现地图找房功能，视口框选加载 + 手动聚合 + 列表联动`
- 高德地图组件 `AmapMap.vue` 完成 Key 配置降级
- CI 流水线修复：ruff lint、npm install、alembic command、env vars

## 周末（06.29-06.30）— 文档审计 + 整理

- 添加项目团队协作规范 `AGENTS.md`，统一分支命名、commit 格式、模块描述
- docs 目录审计：清理重复文件、修复编码问题、建立文档索引
- 创建 `docs/提交/` 文件夹，归档两组长的设计文档初稿
- 前端实现总纲 `frontend-design.md` 归档到 docs

---

## 已完成模块汇总（截至 06.30）

| 模块 | 数据表 | API | Service | 异步任务 |
|------|:---:|:---:|:---:|:---:|
| 用户认证 | users | ✅ | ✅ | - |
| 房源管理 | properties | ✅ | ✅ | - |
| 房源图片 | property_images | ✅ | ✅ | - |
| 预约看房 | bookings | ✅ | ✅ | - |
| 通知推送 | notifications | ✅ | ✅ | ✅ |
| 即时通讯 | chat_sessions / chat_messages | ✅ | ✅ | - |
| 语义搜索 | pgvector embedding | ✅ | ✅ | ✅ |
| 数据导入 | data_imports | ✅ | ✅ | ✅ |
| 管理后台 | - | ✅ | ✅ | - |
| 微信登录 | - | ✅ | ✅ | - |
| 周边设施 | property_pois | ✅ | ✅ | - |
| 地理编码 | - | ✅ | ✅ | - |
| 审计日志 | audit_logs | ✅ | ✅ | - |
| 支付系统 | payments | ✅ | ✅ | - |
| 电子合同 | contracts | ✅ | ✅ | - |
| 公寓机构 | institutes | ✅ | ✅ | - |
| 房源评论 | reviews | ✅ | ✅ | - |
| 搜索收藏 | saved_searches | ✅ | ✅ | - |
| 广告推广 | advertisements / ad_impressions | ✅ | ✅ | - |
| 地图找房 | - | ✅ | ✅ | - |

**技术栈**: FastAPI + SQLAlchemy 2.0（异步） + PostgreSQL 16 + pgvector + Redis + Celery + Docker  
**数据库迁移**: Alembic 共 11 次迁移，20 张表  
**前端**: Vue 3.5 + TypeScript 5.6 + Element Plus 2.9 + Pinia 2.3 + Leaflet  
**测试**: 15 个 pytest 测试文件  

---

## 下周计划

- 前端对接后端新增模型（Review、SavedSearch、Advertisement）
- SMS 短信 + Email 邮件通知实际集成
- 性能优化与压测
- 微信小程序端开发启动

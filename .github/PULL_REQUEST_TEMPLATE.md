---
name: Pull Request
about: 提交代码变更
title: "[模块] 变更简述"
labels: []
assignees: []
---

## 所属模块
<!-- property / booking / payment / contract / auth / chat / map / poi / notification / images / search / admin / wechat -->

## AI 辅助声明
> vibe coding 团队必填：本 PR 中使用了哪些 AI 工具辅助编码？
- [ ] 本 PR 包含 AI 生成的代码
  - AI 工具：<!-- Codex / Claude / Cursor / 其他 -->
  - 涉及文件：<!-- 列出 AI 参与的主要文件 -->
- [ ] 本 PR 全部为手写代码
- [ ] AI 生成的代码已通过人工审查
- [ ] AI 生成的代码已通过完整测试（pytest / vitest）

## 变更说明
<!-- 清晰描述做了什么、为什么这样做 -->

## 关联 Issue
<!-- 如 Closes #123 -->

## 测试清单
- [ ] 后端 pytest 通过（本地或 CI）
- [ ] 前端 vitest 通过（本地或 CI）
- [ ] ruff lint 无新增告警
- [ ] mypy 类型检查通过
- [ ] 手动功能验证完成（列出验证步骤）

## 数据库变更
<!-- 如有模型变更 -->
- [ ] 已生成 Alembic 迁移文件
- [ ] 迁移已测试可正常 upgrade / downgrade

## 依赖变更
<!-- 如有新增/升级依赖 -->
- [ ] 已在 PR 描述中说明新增原因
- [ ] 未引入与现有依赖功能重叠的包
- [ ] `requirements.txt` 或 `package.json` 已更新

## 截图
<!-- 前端变更必填！没有截图的 PR 视为未完成，不得通过 review -->
<!-- AI 无法截图时可先标注"待人工补充"，但必须在 review 前补上 -->

## Checklist
- [ ] 代码遵循 AGENTS.md 中的代码风格规范
- [ ] 未提交调试用 console.log / print
- [ ] 新增环境变量已同步更新 .env.example
- [ ] 无残留的合并冲突标记
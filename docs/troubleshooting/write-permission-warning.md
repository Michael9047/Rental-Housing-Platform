# Write(*.ext) 权限警告反复出现——已解决

> **状态**：✅ 已修复 | **日期**：2026-07-26 | **出现次数**：5 次

---

## 现象

每次与 Claude Code 对话时，系统提醒区域显示多条类似警告：

```
Permission allow rule (.claude\settings.json): Write(*.py) is not matched by file permission checks — only Edit(path) rules are. Use Edit(*.py) instead (Edit rules cover all file-editing tools).
```

涉及的文件类型：`.py` `.ts` `.vue` `.json` `.md` `.env` `.csv` `.html` `.sql` `.sh`（共 10 条）。

---

## 根因

`.claude/settings.json` 的 `permissions.allow` 中错误地添加了 `Write(*.py)` 等规则。

Claude Code 的权限匹配系统将 `Write` 工具归类为文件编辑工具，统一由 `Edit(path)` 规则控制。`Write(path)` 规则**不会被权限检查匹配到**——系统不会报错，但也不会生效，并在每次会话启动时输出上述提醒。

简单说：

| 写法 | 效果 |
|------|------|
| `Write(*.py)` | ❌ 不生效，触发警告 |
| `Edit(*.py)` | ✅ 同时覆盖 Edit + Write 工具 |

---

## 修复

从 `.claude/settings.json` 中删除所有 `Write(*.ext)` 行，仅保留 `Edit(*.ext)` 行。

```diff
-      "Write(*.py)",
-      "Write(*.ts)",
-      "Write(*.vue)",
-      "Write(*.json)",
-      "Write(*.md)",
-      "Write(*.env)",
-      "Write(*.csv)",
-      "Write(*.html)",
-      "Write(*.sql)",
-      "Write(*.sh)",
```

现有的 `Edit(*.py)` 等 15 条规则已经完整覆盖所有需要写的文件类型，无需额外添加。

---

## 预防措施

1. **添加权限规则时只用 `Edit(path)`**，不要使用 `Write(path)`
2. 权限规则的作用域映射（来自官方文档）：
   - `Read(path)` → 覆盖 `Read` 工具
   - `Edit(path)` → 覆盖 `Edit` + `Write` + `NotebookEdit` 工具
   - `Bash(cmd:*)` → 覆盖 `Bash` 工具
   - `Grep(*)` / `Glob(*)` → 各自对应
3. 如果将来再次看到此类警告，检查 `.claude/settings.json` 和 `.claude/settings.local.json` 中是否有 `Write(...)` 条目

---

## 相关文件

- `.claude/settings.json` — 项目级权限配置
- `.claude/settings.local.json` — 本地覆盖配置（不提交）

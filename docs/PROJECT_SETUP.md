# GitHub Projects 任务看板搭建指南

> 本文档指引仓库管理员完成 GitHub Projects 任务看板的搭建与团队推广。

---

## 一、创建 Labels（一次性）

运行以下命令批量创建所有标签：

```powershell
# 确保已安装 gh CLI 并登录
gh auth login

# 批量创建标签
cd "D:\XJTLU Y2S1\Obsidian_Vault\Main\XJTLU\Sem2\Rental Housing Structure"
Get-Content .github\labels.json | python -c "
import json, sys, subprocess
data = json.load(sys.stdin)
for label in data['labels']:
    subprocess.run([
        'gh', 'label', 'create', label['name'],
        '--color', label['color'],
        '--description', label['description'],
        '--force'
    ])
"
```

也可以用 GitHub 网页手动创建：  
`https://github.com/Michael9047/Rental-Housing-Platform/labels`

---

## 二、创建 Project 看板

1. 打开 `https://github.com/Michael9047/Rental-Housing-Platform/projects`
2. 点击 **New project**
3. 模板选择 **Board**
4. 项目名称：`任务看板`
5. 点击 **Create project**

---

## 三、配置看板列

创建后在项目设置中删除默认列，新建以下 4 列：

| 列名 | 含义 |
|------|------|
| 📋 待领取 | 任务池，成员在这里挑活 |
| 🚧 进行中 | 已领取，正在开发 |
| 👀 待 Review | 提了 PR，等 Code Review |
| ✅ 已完成 | PR 合并，问题关闭 |

---

## 四、配置 Workflow 自动化（核心）

进入 Project → **Workflows**，启用以下规则：

### 规则 1：Issue 入列自动归位
- **触发器**：Item added to project
- **动作**：Set field → **Status = 📋 待领取**

### 规则 2：PR 链接 Issue 后自动移 Review
- **触发器**：Pull request linked to item
- **动作**：Set field → **Status = 👀 待 Review**

### 规则 3：PR 合并后自动关 Issue
- **触发器**：Pull request merged
- **动作**：Set field → **Status = ✅ 已完成**
- **额外动作**：Close issue

### 规则 4：Issue 关闭后归档
- **触发器**：Issue closed
- **动作**：Archive item

---

## 五、团队日常使用流程

```
PM / 任何人                    开发者                      Reviewer
───────────                  ─────────                  ────────
建 Issue（用模板）            打开看板                    看到 👀 待 Review
选模块 + 优先级标签           拖任务到 🚧 进行中           Review 代码
→ 自动入 📋 待领取            assign 给自己              Approve / 提意见
                             开分支 feat/xxx             合并 PR
                             开发 + 提 PR                 → 自动移到 ✅
                             PR 描述写 Closes #12
                             → Issue 自动入 👀 待 Review
```

---

## 六、Issue 与分支的联动技巧

在 PR 描述中使用关键词，GitHub 会自动关联：

```
Closes #12          → 合并后自动关闭 Issue #12
Fixes #12           → 同上
Resolves #12        → 同上
```

分支命名遵循 AGENTS.md 规范：`feat/map-geocoding`、`fix/payment-callback` 等。

---

## 七、看板筛选与视图

建议创建以下 Saved Views，方便聚焦：

| 视图名 | 筛选条件 | 用途 |
|--------|----------|------|
| 我的任务 | `assignee:@me` | 只看自己领的活 |
| 高优任务 | `label:high` | 紧急任务一览 |
| 后端任务 | `label:backend` | 后端同学专用 |
| 前端任务 | `label:frontend` | 前端同学专用 |
| 未分配 | `no:assignee` | 方便分配任务 |

---

## 八、Label 速查表

### 任务类型
`task` `bug` `enhancement` `question` `documentation`

### 优先级
`high` `medium` `low`

### 技术栈
`frontend` `backend` `wechat-miniprogram`

### 业务模块
`property` `booking` `payment` `contract` `auth` `chat`
`map` `poi` `notification` `images` `search` `admin` `wechat`

---

## 九、通知配置

在 Project 设置中开启 Slack / 邮件通知，关注以下事件：
- 新 Issue 添加
- Issue 被分配
- PR 被 Review

如果团队用飞书为主，可以用 GitHub App "Feishu Bot" 把通知同步到飞书群。

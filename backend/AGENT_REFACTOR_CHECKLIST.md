# Agent 层重构清单

> 目标：从 EstateWise 翻译的 21 Agent 通用架构 → 中国学生租房平台的 7 Agent 精简架构

---

## 阶段一：删除（减少维护负担）🔴 高优先

### 1.1 删除 MoE 专家组（7 个文件）

**理由：** MoE 是为美国多房源对比场景设计的，你的场景是单一搜索→推荐。5 个专家并行分析同一批房源对用户没有价值——用户不关心"空间利用率专家怎么说"，只想要一个清晰的推荐结果。

**删除文件：**
```
app/services/agentic/agents/experts/area_expert.py
app/services/agentic/agents/experts/price_expert.py
app/services/agentic/agents/experts/commute_expert.py
app/services/agentic/agents/experts/lifestyle_expert.py
app/services/agentic/agents/experts/space_expert.py
app/services/agentic/agents/experts/amenity_expert.py
app/services/agentic/agents/experts/merger_agent.py
app/services/agentic/agents/experts/__init__.py
```

**同时修改：**
- `agents/registry.py` — 删除 7 个 MoE Agent 的注册代码
- `orchestration/execution_dag.py` — 删除 `COMPLEX_SEARCH_DAG` 和 `enable_moe` 参数
- `orchestration/supervisor.py` — 删除 `_run_amenity_expert()` 方法、`_moe_expert_keys` 列表、`hard_filter_empty` 逻辑

### 1.2 删除冗余 Agent（4 个定义）

**理由：** 职责已被其他 Agent 或工具覆盖。

| 删除的 Agent | 理由 |
|---|---|
| `planner_agent` | 任务分解对当前场景过度设计，Supervisor 的 DAG 模板已足够 |
| `ranking_agent` | 排序去重已由 `score_properties` + `gap_detect` 工具完成 |
| `relation_agent` | 房源相似关系分析——学生租房不需要 |
| `context_agent` | 上下文管理由 search_state 完成，不需要独立 Agent |

**修改文件：**
- `agents/registry.py` — 删除 4 个 Agent 的注册代码
- `agents/planner_agent.py` — 可删（如无其他引用）
- `agents/ranking_agent.py` — 可删
- `agents/relation_agent.py` — 可删
- `agents/context_agent.py` — 可删

### 1.3 删除 ComplianceAgent

**理由：** 纯 LLM 回答法律问题 = 危险。没有接入中国租赁法规库，不应假装懂法律。

**操作：**
- 删除 `agents/compliance_agent.py`
- `agents/registry.py` — 删除注册
- 如有法规咨询需求，改为 FAQ 条目（如"押金一般多少""合同要注意什么"）让 `faq_agent` 处理

**删除后总数：21 → 7 个核心 Agent**

---

## 阶段二：重写 System Prompt（中文化+领域化）🔴 高优先

### 2.1 重写 7 个 Agent 的 System Prompt

**目标：** 全部替换为中文、学生租房语境、XJTLU 场景。

**涉及文件：** `orchestration/supervisor.py` → `_build_system_prompt()` 方法（行 1223-1313）

**每个 Agent 的新 prompt 要点：**

| Agent | Prompt 要点 |
|---|---|
| `filter_agent` | 从中文消息提取：区域（如"苏州工业园区"）、预算（元/月）、户型（单间/一居/合租）、离校距离、是否独卫 |
| `search_agent` | 先提取条件→搜索→评分→推荐。中文回复格式：先总量，再逐套介绍（月租/区域/距校时间/亮点），不编造不存在的数据 |
| `commute_agent` | 计算到西交利物浦大学（或用户指定的其他学校）的公交/步行/骑行时间。标注是否需要换乘 |
| `poi_agent` | 查询周边：超市/餐馆/地铁站/公交站/打印店（学生常用）。输出距离和步行时间 |
| `compare_agent` | 对比维度：价格、通勤、面积、配套。输出对比表+建议 |
| `synthesizer_agent` | 根据漏斗阶段调整语气：explore引导→calibrate比较→narrow分析→compare推荐→decide行动。中文口语化 |
| `market_agent` | 市场概况：该区域均价、户型分布。帮助用户校准预算预期（如"园区单间一般在1500-2500元"） |

### 2.2 重写 DAG 模板中的 Simple Search 模板

**文件：** `orchestration/execution_dag.py`

当前 `SEARCH` 模板是 `filter → search → synthesizer`，改为支持通勤/POI 的**可选并行**：

```python
# 简单搜索：filter → search → synthesizer
# 有通勤需求时：search 完成后并行 run commute_agent
# 有POI需求时：search 完成后并行 run poi_agent
```

不需要 MoE 专家组，但可以在 synthesizer 之前加一个可选的数据丰富层。

---

## 阶段三：修复数据缺口 🟡 中优先

### 3.1 通勤 Agent：支持等时圈筛选

**当前问题：** `commute_calc` 只能正向计算（给房源→回时间）。用户问"学校30分钟以内有哪些房源"时只能逐个算。

**方案：**
- 短期：优化 prompt，让 Agent 先用 `property_search` 获取候选，再选取 top 3 调用 `commute_calc`，告诉用户"这是距离最近的3套房源的通勤情况"
- 长期：在 `commute_service` 中增加 isochrone 能力（调高德等时圈 API），实现真正的"30分钟圈"筛选

### 3.2 POI 数据：补充学生常用设施类型

**当前问题：** POI 查询用的是通用分类（restaurants/schools/parks），缺少学生场景。

**方案：**
- 在 `poi_lookup` 的 handler 中增加 `print_shop`（打印店）、`convenience_store`（便利店）、`canteen`（食堂）等分类
- 确认 POI 数据表中有这些类型的覆盖

### 3.3 FAQ：补充中国租房常见问题

**文件：** `app/services/agent_faq.py`

**需要补充的 FAQ 条目：**
- 押金一般多少（一个月房租 vs 两个月）
- 合同注意事项
- 水电费怎么算
- 短租 vs 长租区别
- 合租注意事项
- 学校宿舍 vs 校外租房对比

---

## 阶段四：精简代码复杂度 🟡 中优先

### 4.1 评估是否删除 Handoff 链模式

**涉及代码：** `supervisor.py` 中 ~250 行（行 193-535）

**当前状态：** `handle_message_handoff()` 从未被路由触发（路由只有 default/expert/handoff，但 handoff 模式需要显式设置）。

**建议：** 删除 `handle_message_handoff()` 及所有 `_handoff_*` 相关代码。Handoff 链的设计前提是"Agent 之间互相不知道对方的能力"——但你的 Agent 由 Supervisor 统一编排，DAG 模板已经明确了调用顺序，handoff 是多余的一层。

**如果保留：** 至少确保它被测试过，而不是一直留着不用的死代码。

### 4.2 统一 AGENT_MODE 配置

**当前问题：**
- `.env` 里设置的是 `AGENT_MODE=supervisor`
- `config.py` 注释写的是 `"expert"` 模式
- 路由代码里检查的是 `"expert"` 和 `"handoff"`

**修复：** 统一命名。建议用 `AGENT_MODE=multi-agent` 或 `AGENT_MODE=expert`。确保 `.env`、`config.py` 注释、路由代码三者一致。

### 4.3 统一 Agent 执行方式

**当前问题：** 同一个 Supervisor 中，Agent 有三种执行方式：
- cart/faq → 直接 Python 调用（无 LLM）
- search → 优先 ReAct，降级到旧管线
- filter/commute/poi/market → ReAct loop

**建议：** 这是个合理的分层，但需要在代码中加注释说明为什么要区分。搜索降级到旧管线尤其需要文档说明（"因为旧管线的渐进放宽+评分是确定性的，比 LLM ReAct 重新编排更可靠"）。

---

## 阶段五：测试与验证 🟢 正常优先

### 5.1 写 Agent 层单元测试

**当前状态：** `tests/test_agent.py` 只测了 legacy AgentService，多 Agent 层零测试覆盖。

**需要测试：**
- [ ] 7 个核心 Agent 在无 LLM 时能正确降级（返回兜底回复而非崩溃）
- [ ] 每个 Agent 的 tool handler 绑定正确（参数传入→返回预期格式）
- [ ] DAG 拓扑排序不产生死循环
- [ ] filter_agent（ReAct max_iterations=2）在两次迭代后必定停止
- [ ] supervisor 所有意图分类走规则兜底时不崩溃

### 5.2 端到端场景测试

用真实中文用户消息验证：

- [ ] "园区2000以内的单间" → filter提取条件 + search搜索 + synthesize推荐
- [ ] "到西交利物浦大学地铁30分钟以内的" → commute 计算 + 结果筛选
- [ ] "附近有超市和打印店的" → POI 查询 + 结果合并
- [ ] "押金一般多少" → FAQ 直接匹配（不走 LLM）
- [ ] "把我刚才看的那套加入清单" → cart 操作
- [ ] "帮我对比购物车里的三套" → compare 多维度对比

---

## 改动文件总览

```
需删除的文件 (12个):
  agents/experts/area_expert.py
  agents/experts/price_expert.py
  agents/experts/commute_expert.py
  agents/experts/lifestyle_expert.py
  agents/experts/space_expert.py
  agents/experts/amenity_expert.py
  agents/experts/merger_agent.py
  agents/experts/__init__.py
  agents/planner_agent.py
  agents/ranking_agent.py
  agents/relation_agent.py
  agents/context_agent.py
  agents/compliance_agent.py

需修改的文件 (5个):
  agents/registry.py          — 精简为 7 Agent
  orchestration/execution_dag.py — 删除 COMPLEX_SEARCH_DAG，精简模板
  orchestration/supervisor.py — 重写 prompt，删除 MoE/handoff 代码
  app/core/config.py          — 统一 AGENT_MODE 命名
  .env                        — 统一 AGENT_MODE 值

需新增/更新的文件 (2个):
  tests/test_agentic.py       — 多 Agent 层测试 (新增)
  app/services/agent_faq.py   — 补充中国租房 FAQ (更新)
```

---

## 执行顺序建议

```
第一轮（1-2小时）：
  1. 删除 12 个文件
  2. 修改 registry.py + execution_dag.py
  3. 运行 pytest 确认不崩溃

第二轮（2-3小时）：
  4. 重写 7 个 Agent 的 system prompt（supervisor.py）
  5. 统一 AGENT_MODE 配置
  6. 写 5 个端到端场景测试

第三轮（1小时）：
  7. 补充 FAQ 条目
  8. 写 Agent 降级测试
  9. 删除或保留 handoff 代码（做决定）
```

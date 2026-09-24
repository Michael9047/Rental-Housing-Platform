# PR #43 AI 搜索完整流程图

> 从用户输入到最终响应，途经 Dispatcher（编排层）→ SearchAgent（执行层）→ LLM（生成层）

---

## 一、总览

```
用户输入
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Dispatcher (编排层)                       │
│                                                             │
│  _prepare_context()                                         │
│    ├─ 恢复记忆 (session state + long-term prefs)            │
│    ├─ 分类意图 (search/compare/cart/faq)                    │
│    └─ 解析指代 ("第二套" → property_id)                     │
│                                                             │
│  _prepare_search()                                          │
│    ├─ 查询理解 (NL → 结构化条件 + 改写查询)                  │
│    ├─ 合并筛选 (5 层优先级)                                  │
│    └─ 位置守卫 (无区域/学校时先反问)                         │
│                                                             │
│  _execute_search()  ─── 调用 SearchAgent ───┐               │
│                                             │               │
│  _build_filter_patch()  ← 生成筛选回填       │               │
│  _persist_messages()     ← 原子持久化        │               │
└─────────────────────────────────────────────│───────────────┘
                                              │
                                              ▼
                              ┌───────────────────────────────┐
                              │    SearchAgent._pipeline()    │
                              │         (执行层)              │
                              │                               │
                              │  ① 双路混合召回               │
                              │  ② 通勤数据挂载               │
                              │  ③ 结构化约束匹配             │
                              │  ④ 宽召回池补充（如需）       │
                              │  ⑤ POI 数据挂载               │
                              │  ⑥ 约束消融（如需）           │
                              │  ⑦ 7 信号重排                 │
                              │  ⑧ 事实边界打包               │
                              │  ⑨ LLM 生成回复               │
                              │  ⑩ 组装结果                   │
                              └───────────────────────────────┘
```

---

## 二、Dispatcher 编排层

```
POST /api/v1/agent/sessions/{id}/messages/stream
  │
  ▼
dispatch_stream()
  │
  ├─ ① _prepare_context(session, chat_session, user_id, message,
  │                      filters, context_filters, ...)
  │   │
  │   ├─ AgentMemoryService.load(message)
  │   │   ├─ 查 agent_session_states     → 会话筛选/阶段/指代映射/上轮结果
  │   │   ├─ 查 agent_user_memories      → 长期偏好 + 置信度
  │   │   ├─ 查 chat_messages            → 最近 12 条历史
  │   │   └─ _resolve_references()       → "第二套" → property_id=42
  │   │       返回: RuntimeMemory{state, memory, reference_resolution}
  │   │
  │   ├─ load_packed_history()           → 压缩历史 (8000 字预算)
  │   │
  │   ├─ classify_message(message, history) → intent="search"
  │   │
  │   └─ 组装 _DispatchContext → 不可变请求上下文
  │
  ├─ ② SSE: yield {event: "status", thinking_steps: [...]}
  │
  ├─ ③ if intent == "search":
  │       _prepare_search(ctx)
  │       │
  │       ├─ understand_query(message, previous_filters, rolling_summary)
  │       │   │                                        ↑ 会话上下文
  │       │   ├─ 确定性正则 (始终执行):
  │       │   │   "NUS 附近 studio 2500以内"
  │       │   │     → institution=NUS, room_type=studio, price_max=2500
  │       │   │   "便宜一点"
  │       │   │     → price_max *= 0.85 (相对修改)
  │       │   │   "不要独卫了"
  │       │   │     → remove_values["room_type"]="ensuite"
  │       │   │
  │       │   └─ LLM 增强 (仅 LLM 可用时):
  │       │         → rewritten_query="新加坡国立大学附近单间公寓月租2500以下"
  │       │         → query_kind="exact"
  │       │         → explicit_memory_fields=["institution", "room_type"]
  │       │
  │       └─ memory_service.merge_filters()
  │            合并优先级:
  │              长期偏好(置信度≥0.75)
  │              < 当前会话状态
  │              < 搜索页 context_filters (前端左侧筛选栏)
  │              < 本轮 NL 提取
  │              < 显式 filters
  │            列表字段增量合并，删除语义识别
  │
  │    ┌─ 位置守卫检查 ───────────────────────────────────┐
  │    │ 首次搜索且无 country/district/institution?        │
  │    │ → 不搜索，直接反问 "请问在哪个国家/城市/学校?"     │
  │    └──────────────────────────────────────────────────┘
  │
  ├─ ④ _execute_search(ctx)  ──→ 调用 SearchAgent (见第三部分)
  │
  ├─ ⑤ memory_service.save_search()  ← 写入审计
  │      写入: agent_search_runs (1 行)
  │            agent_search_candidates (N 行，带分项分和来源)
  │
  ├─ ⑥ _build_filter_patch(understanding, effective_filters)
  │      检查 14 字段白名单 → 只回填硬条件，不过滤软偏好
  │      例: {price_max: 2500}  ← 前端左侧筛选栏同步
  │
  └─ ⑦ _persist_messages(ctx, result)
        写入: chat_messages (user + assistant 各一行)
        更新: agent_session_states (filters_json, last_search_json, rolling_summary)
```

---

## 三、SearchAgent 执行层（_pipeline 核心 10 步）

```
_pipeline(message, filters, understanding, stage)
  │
  │  入参说明:
  │    message     = 用户原始输入 (已由 Dispatcher 处理过上下文)
  │    filters     = 已合并的 effective_filters (5 层合并结果)
  │    understanding = QueryUnderstanding (含 extracted_filters + rewritten_query)
  │    stage       = "explore" | "compare" | "decide"
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ① 双路混合召回                                              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  语义路: search_unit_types(query_vec, district, price, ...)   ║
║    SELECT * FROM unit_types                                   ║
║    JOIN institutes ON ...                                     ║
║    WHERE ...                                                  ║
║    ORDER BY embedding.cosine_distance(query_vec) ASC          ║
║    LIMIT 60                                                   ║
║    └── pgvector HNSW 索引，DB 内完成，不出应用层              ║
║                                                               ║
║  结构化路: search_unit_types(None, district, price, ...)      ║
║    同上但无向量排序，纯 WHERE 过滤                            ║
║    LIMIT 30                                                   ║
║                                                               ║
║  → merge_recall_legs(): 按 unit_type.id 去重合并              ║
║  → recall_pool: [{unit_type, institute, available_rooms}, ..] ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ② 通勤数据挂载 (_attach_commute_context)                    ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  for each candidate:                                          ║
║    查 room_commutes 表 (university_id + room_id)              ║
║    → 注入 _commute_minutes, _commute_source                   ║
║    (无数据 → source="missing")                                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ③ 结构化约束匹配 (candidate_matches_filters)                ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  逐条检查 20+ 维度，全部通过才标记为 strict_match:           ║
║                                                               ║
║  ┌─ 地理位置 ─────────────────────────────────────┐          ║
║  │ country:  "SG" in (institute.country, city...)  │          ║
║  │ district: "苏州" in (district, city, address..)  │          ║
║  └────────────────────────────────────────────────┘          ║
║  ┌─ 价格 ─────────────────────────────────────────┐          ║
║  │ price_min ≤ unit_type.base_rent ≤ price_max    │          ║
║  └────────────────────────────────────────────────┘          ║
║  ┌─ 房型 ─────────────────────────────────────────┐          ║
║  │ bedrooms: unit_type.bedrooms == 1              │          ║
║  │ room_type: studio → bedrooms==0 OR "单间"      │          ║
║  │            ensuite → "独卫" in amenities       │          ║
║  └────────────────────────────────────────────────┘          ║
║  ┌─ 面积 / 卫浴 / 设施 / 租期 / 入住日 ──────────┐          ║
║  │ area:   area_min ≤ unit_type.area_sqm ≤ area_max│         ║
║  │ amenity: 所有需求设施 ⊆ candidate 设施集合     │          ║
║  │ lease:  unit_type.min_stay ≤ 用户要求          │          ║
║  │ move_in: unit_type.available_from ≤ 用户要求   │          ║
║  └────────────────────────────────────────────────┘          ║
║  ┌─ 通勤 / POI ───────────────────────────────────┐          ║
║  │ commute: _commute_minutes ≤ target             │          ║
║  │ poi:     _poi_distances[type] ≤ max_distance   │          ║
║  │ female_only: institute.female_only == 要求     │          ║
║  └────────────────────────────────────────────────┘          ║
║                                                               ║
║  → strict_matches: 满足所有约束的候选列表                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ├─ strict_matches ≥ min_results(3)? ──YES──→ 跳到 ⑤
  │
  │  NO
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ④ 宽召回池补充 + 旧数据 fallback（如需）                    ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  broad_semantic: 去掉 district/price/bedrooms 限制            ║
║  broad_structured: 同上，纯结构化                             ║
║  → 合并后排除已知 ID → 追加到 recall_pool                     ║
║                                                               ║
║  旧数据兼容 (HEAD 删除):                                      ║
║  if recall_pool 仍为空 → _legacy_recall() 查旧 properties 表  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ⑤ POI 数据挂载                                              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  load_unit_type_poi(unit_type_ids) → 查 property_pois 表     ║
║    → poi_by_unit_type: {unit_type_id: {transit: 350m, ...}}  ║
║                                                               ║
║  attach_poi_distances(recall_pool, poi_by_unit_type)          ║
║    → 每候选注入 _poi_distances                               ║
║                                                               ║
║  if 用户有 POI 偏好: rank_by_poi(recall_pool, ...)           ║
║    → 按 POI 距离软重排 (仅调序，不去掉)                      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ⑥ 约束消融 (apply_constraint_ablation)                      ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  if 严格匹配 ≥ 3: 不消融，直接用 strict_matches              ║
║                                                               ║
║  if 严格匹配 = 1-2:                                          ║
║    → 保留严格结果，返回可点击放宽建议 chips                  ║
║    → 不自动应用放宽                                          ║
║                                                               ║
║  if 严格匹配 = 0:                                            ║
║    → 逐项试验放宽 (按策略顺序):                               ║
║                                                               ║
║      策略顺序 (从温和到激进):                                 ║
║      ① price_max  +20%     "预算上调至 3000"                 ║
║      ② price_min  -20%     "最低预算下調"                    ║
║      ③ district   移除     "暂不限制区域"                    ║
║      ④ property_type 移除  "暂不限制房源类型"                ║
║      ⑤ room_type  移除     "暂不限制房型"                    ║
║      ⑥ bedrooms   移除     "暂不限制卧室数"                  ║
║      ⑦ area_min   移除                                       ║
║      ⑧ area_max   移除                                       ║
║      ⑨ bathrooms  移除                                       ║
║      ⑩ amenities  移除                                       ║
║      ⑪ commute    移除                                       ║
║      ⑫ poi        移除                                       ║
║      ⑬ max_lease  移除                                       ║
║                                                               ║
║    → 选第一个能恢复 ≥3 结果的方案                             ║
║    → hard_filters 中的字段不自动放宽                          ║
║    → 自动应用，并在回复中告知用户放宽了什么                   ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ⑦ 7 信号重排 (rerank_candidates)                            ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  每个候选计算 7 个 0-1 分数，加权求和 → 0-100:              ║
║                                                               ║
║  ┌─────────────┬──────┬──────────────────────────────────┐   ║
║  │ 信号         │ 权重  │ 计算方式                         │   ║
║  ├─────────────┼──────┼──────────────────────────────────┤   ║
║  │ semantic    │ 32%  │ pgvector cosine_distance (DB 层)  │   ║
║  │ lexical     │ 12%  │ 中文 bigram + 英文 token 命中覆盖  │   ║
║  │ price       │ 18%  │ |price - target₉₀%| / spread     │   ║
║  │ commute     │ 14%  │ 1.0 - (通勤-目标)/max(目标,1)      │   ║
║  │ poi         │ 10%  │ 周边设施距离归一化                 │   ║
║  │ quality     │ 8%   │ 7 项完整度检查 (名称/价格/面积...) │   ║
║  │ constraint  │ 6%   │ 全过=1.0, 放宽后过=0.65           │   ║
║  └─────────────┴──────┴──────────────────────────────────┘   ║
║                                                               ║
║  final_score = Σ(signal × weight) × 100                      ║
║                                                               ║
║  排序: score↓ → available_rooms↓ → price↑                    ║
║                                                               ║
║  每候选注入:                                                  ║
║    _score_breakdown: {semantic: 85.3, lexical: 62.1, ...}    ║
║    _final_score: 78.4                                        ║
║    _rank: 1                                                  ║
║    _source_metadata: {property: "unit_types", commute: ...}  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ⑧ 事实边界打包 (pack_grounded_candidates)                   ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  explore 阶段 → top 3                                        ║
║  compare/decide 阶段 → top 5                                 ║
║                                                               ║
║  每个候选生成:                                                ║
║    facts: {name, price, bedrooms, area, commute, amenities..} ║
║    sources: {property, inventory, commute, poi, semantic}     ║
║      → "unit_types" / "rooms" / "missing"                    ║
║                                                               ║
║  上下文限制: 12,000 字符                                      ║
║                                                               ║
║  注入 grounding_policy 到 system prompt:                      ║
║    "只能使用 candidates.facts 中的事实"                       ║
║    "sources 标为 missing → 说暂无数据/建议确认"               ║
║    "只能提到候选列表中的房源名称和编号"                       ║
║    "不能创造新房源或修改排名"                                 ║
║    "推荐 ID、名次、分数由后端确定"                            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ⑨ LLM 生成回复                                              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  非流式: complete_text(system=RECOMMEND_SYSTEM_PROMPT,        ║
║                         user=grounded_context_JSON,           ║
║                         max_tokens=2000)                      ║
║                                                               ║
║  流式: LLM streaming API → 逐 token → SSE yield              ║
║                                                               ║
║  RECOMMEND_SYSTEM_PROMPT 结构 (四段式):                       ║
║    ① 需求确认: 复述理解                                       ║
║    ② 逐套介绍: 每套用 facts 中的数据                          ║
║    ③ 横向比较: 价格/通勤/设施对比                             ║
║    ④ 总结建议: 条件有无放宽、下一步建议                       ║
║                                                               ║
║  降级: LLM 不可用 → _fallback_reply() 规则摘要               ║
║         列出 top 5 的关键信息 (名/价格/户型/区域/通勤)       ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
  │
  ▼
╔═══════════════════════════════════════════════════════════════╗
║  ⑩ 组装结果                                                  ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  return {                                                    ║
║    recommendations: [{                                       ║
║      property_id, rank, final_score, score_breakdown,        ║
║      match_reason, pros, cons, poi_distances, source_metadata║
║    }, ...],                                                  ║
║    reply: "...",          # LLM 生成的推荐文字               ║
║    guided_options: [...], # 可点击建议 chips                 ║
║    relaxation_trace: [...],# 放宽轨迹 (哪项被放宽了)         ║
║    effective_filters: {}, # 实际使用的筛选条件               ║
║    sources: [...],        # 数据来源标签                     ║
║    latency_ms: 1234,      # 管线耗时                         ║
║  }                                                           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## 四、SSE 流式时间线

```
Client                          Server
  │                                │
  │  POST /sessions/{id}/messages/stream
  │  {message, context_filters}    │
  │ ─────────────────────────────→ │
  │                                ├─ _prepare_context()     ~50ms
  │                                │
  │  event: status                 │
  │  {intent:"recommend",          │
  │   thinking_steps:[...]}        │
  │ ←───────────────────────────── │
  │                                ├─ _prepare_search()      ~200ms
  │                                │  (query understanding + merge filters)
  │                                │
  │  event: status                 │
  │  {query_rewrite:{...},         │
  │   thinking_steps:[...]}        │
  │ ←───────────────────────────── │
  │                                ├─ SearchAgent._pipeline() ~300ms
  │                                │  (recall + filter + rerank)
  │                                │
  │  event: token                  │
  │  {token:"为您"}                │
  │ ←───────────────────────────── │
  │  event: token                  │
  │  {token:"找到"}                │
  │ ←───────────────────────────── │  LLM 流式生成 ~10s
  │  event: token                  │
  │  {token:"3套"}                 │
  │ ←───────────────────────────── │
  │  ... 逐 token ...              │
  │                                │
  │  event: meta                   │
  │  {filter_patch:{price_max:2500},│
  │   recommendations:[...],       │
  │   state_summary:{...},         │
  │   sources:[...]}               │
  │ ←───────────────────────────── │
  │                                ├─ _persist_messages()    ~100ms
  │                                │  (保存消息+记忆+审计)
  │  [DONE]                        │
  │ ←───────────────────────────── │
```

---

## 五、关键数据结构

### 候选对象（在管线各步骤中流转）

```python
candidate = {
    # ── 数据源 ──
    "unit_type":     UnitType实例,     # 户型 ORM 对象
    "institute":     Institute实例,    # 公寓 ORM 对象

    # ── 步骤 ② 注入 ──
    "_commute_minutes": 25,            # 通勤分钟
    "_commute_source":  "api",         # "api" | "lookup_table" | "missing"

    # ── 步骤 ③ 检查 ──
    # (通过 candidate_matches_filters 逐维检查)

    # ── 步骤 ⑤ 注入 ──
    "_poi_distances": {                # 周边设施距离
        "transit": 350,                # 最近地铁/公交站 (米)
        "supermarket": 500,
        "hospital": 1200,
    },
    "_poi_score": 78.5,               # POI 综合分 (0-100)

    # ── 步骤 ⑦ 注入 ──
    "embedding_score": 0.853,         # pgvector cosine 相似度 (0-1)
    "_score_breakdown": {             # 7 信号分项分
        "semantic":   85.3,
        "lexical":    62.1,
        "price":      91.0,
        "commute":    72.5,
        "poi":        78.5,
        "quality":    87.5,
        "constraint": 100.0,
    },
    "_final_score": 82.4,             # 综合分 (0-100)
    "_rank": 1,                        # 排名
    "_source_metadata": {              # 数据来源追踪
        "property":  "unit_types",
        "institute": "institutes",
        "commute":   "room_commutes",
        "poi":       "property_pois",
        "semantic":  "unit_types.embedding",
        "missing_fields": [],          # 缺少哪些数据
    },

    # ── 辅助字段 ──
    "available_rooms": 1,              # 可租库存
    "min_price": 2000,                 # 最低价
    "_property_id": 42,               # 展示用 ID
    "_unit_type_id": 15,              # 户型 ID
}
```

### 返回给前端的 Recommendation

```typescript
{
  property_id: 42,
  rank: 1,
  final_score: 82.4,
  score_breakdown: {
    semantic: 85.3, lexical: 62.1, price: 91.0,
    commute: 72.5, poi: 78.5, quality: 87.5, constraint: 100.0
  },
  match_reason: "综合匹配 82 分 · XXX公寓 · 1室 · 1间可租",
  pros: ["预算贴合", "需求语义匹配", "信息完整"],
  cons: [],
  poi_distances: { transit: 350, supermarket: 500 },
  source_metadata: { property: "unit_types", commute: "room_commutes", ... }
}
```

---

## 六、与 HEAD 搜索流程的对比

```
HEAD (当前)                          PR #43
───────                              ──────

用户消息                             用户消息
  │                                    │
  LLM 提取条件 (JSON, 可能失败)        ├─ 记忆恢复 (session + long-term)
  │                                    ├─ 意图分类 + 指代解析
  手动 or 合并 filters                 ├─ 正则 + LLM 查询理解 (正则兜底)
  │                                    ├─ 5 层筛选合并
  search_unit_types()                  │
  (单路, 无向量下推)                   ├─ 位置守卫 (无区域则反问)
  │                                    │
  拉 500 条向量到 Python               ├─ 双路召回 (语义 HNSW + 结构化)
  JSON 反序列化                        │   pgvector SQL 下推
  NumPy 逐条算 cosine                  │
  │                                    ├─ 通勤挂载
  取前 3 条                            │
  │                                    ├─ 20+ 维约束检查
  手写 JSON 丢给 LLM                   │
  │                                    ├─ 约束消融 (0 结果自动放宽)
  LLM 生成 (可能编造)                  │
  │                                    ├─ POI 挂载 + 软重排
  返回 (flat list, 无分数)             │
                                       ├─ 7 信号重排 (每套 0-100 分)
                                       │
                                       ├─ 防幻觉事实边界打包
                                       │
                                       ├─ LLM 生成 (只能引用 facts)
                                       │
                                       ├─ filter_patch 回填
                                       │
                                       ├─ 搜索审计持久化
                                       │
                                       └─ 返回 (ranked, scored, sourced)
```

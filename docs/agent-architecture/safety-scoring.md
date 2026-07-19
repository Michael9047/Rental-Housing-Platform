# 安全评分子系统

> 2026-07-13 | Michael

---

## 定位

为对比 Agent 提供可量化的安全评分。分别对接英国 (Police.uk) 和新加坡 (data.gov.sg) 两个数据源，统一输出 0-100 的安全评分。

---

## 整体架构

```mermaid
graph TB
    subgraph Input["输入"]
        LatLng["房源坐标 (lat, lng)"]
        Country["国家标识 (UK / SG)"]
    end

    subgraph SafetyScoring["SafetyScoring Service"]
        Router{"国家路由"}

        subgraph UK["英国管线"]
            GeocodeUK["坐标 → Postcode<br/>(Postcodes.io)"]
            PoliceAPI["Police.uk API<br/>/crimes-street/all-crime<br/>1 英里半径"]
            UKAgg["聚合 14 类犯罪<br/>per 1000 residents"]
            UKBenchmark["与城市/LSOA 均值对比"]
        end

        subgraph SG["新加坡管线"]
            GeocodeSG["坐标 → NPC 辖区<br/>(边界映射)"]
            DataGovAPI["data.gov.sg API<br/>Selected Major Offences<br/>by NPC, Annual"]
            SGAgg["聚合 5 类可防罪案<br/>per 1000 residents"]
            SGBenchmark["与全国/NPC 均值对比"]
        end
    end

    subgraph Output["统一输出"]
        Score["safety_score: 0-100"]
        Breakdown["category_breakdown<br/>{violent, burglary, theft...}"]
        Comparison["comparison<br/>vs_city_avg: 'below'/'average'/'above'"]
        Summary["summary_text<br/>'该区域暴力犯罪率低于伦敦均值...'"]
    end

    LatLng --> Router
    Country --> Router
    Router --> UK
    Router --> SG
    UK --> Score
    SG --> Score
    UK --> Breakdown
    SG --> Breakdown
    UK --> Comparison
    SG --> Comparison
    Score --> Summary
    Breakdown --> Summary
    Comparison --> Summary
```

---

## 英国: Police.uk API 对接

```mermaid
sequenceDiagram
    participant SS as SafetyScoring
    participant PC as Postcodes.io
    participant Police as data.police.uk API

    SS->>SS: 输入: lat=51.5074, lng=-0.1278

    Note over SS,Police: Step 1: 获取区域基准

    SS->>PC: GET /postcodes?lat=51.5074&lon=-0.1278
    PC-->>SS: {postcode: "WC1B 4BA", lsoa: "Camden 028B"}

    Note over SS,Police: Step 2: 拉取街道级犯罪数据

    SS->>Police: GET /api/crimes-street/all-crime<br/>?lat=51.5074&lng=-0.1278&date=2026-04
    Police-->>SS: [{category, location, month, outcome}...]

    Note over SS,Police: Step 3: 聚合分析

    SS->>SS: 按 14 类聚合计数
    SS->>SS: 计算 per-1000-residents 比率<br/>(基于 LSOA 人口)
    SS->>SS: 与伦敦均值对比
    SS->>SS: 生成 0-100 评分

    Note over SS: 评分逻辑:
    Note over SS: violent_crime 权重 35%
    Note over SS: burglary 权重 25%
    Note over SS: antisocial_behaviour 权重 15%
    Note over SS: robbery 权重 15%
    Note over SS: other 权重 10%
```

### 英国犯罪类别 (14 类)

| 类别 | 对学生的威胁 | 评分权重 |
|------|-------------|----------|
| `violent-crime` | 🔴 高 | 35% |
| `burglary` | 🔴 高 | 25% |
| `robbery` | 🟠 中高 | 15% |
| `anti-social-behaviour` | 🟡 中 | 15% |
| `vehicle-crime` | 🟡 中 | 5% |
| `criminal-damage-arson` | 🟡 中 | 3% |
| `drugs` | 🟡 中 | 2% |
| `other-theft` | 🟢 低 | — |
| `shoplifting` | 🟢 低 | — |
| `bicycle-theft` | 🟢 低 | — |
| `theft-from-the-person` | 🟠 中高 | 归入 robbery |
| `possession-of-weapons` | 🔴 高 | 归入 violent |
| `public-order` | 🟡 中 | 归入 antisocial |
| `other-crime` | — | — |

### 评分公式

```
zone_crime_rate = Σ(category_count × weight) / lsoa_population × 1000
city_avg_rate   = Σ(city_category_count × weight) / city_population × 1000

ratio = zone_crime_rate / city_avg_rate

safety_score = clamp(100 - (ratio × 50), 10, 100)
             = ratio = 1.0 (等于均值) → 50 分
             = ratio = 0.5 (低于均值一半) → 75 分
             = ratio = 2.0 (高于均值一倍) → 0 分 → clamp 到 10
```

### 注意事项

- **苏格兰不覆盖** — 需要后续对接 SIMD (Scottish Index of Multiple Deprivation)
- **数据滞后 2-3 个月** — 标注数据月份
- **位置匿名化** — Police.uk 将犯罪位置偏移到最近街道中点，1 英里半径足够覆盖此误差

---

## 新加坡: data.gov.sg 对接

```mermaid
sequenceDiagram
    participant SS as SafetyScoring
    participant Gov as data.gov.sg API
    participant Geo as NPC Boundary Lookup

    SS->>SS: 输入: lat=1.3039, lng=103.8318

    Note over SS,Geo: Step 1: 确定 NPC 辖区

    SS->>Geo: 坐标 → NPC 辖区映射<br/>(预加载 35 个 NPC 边界多边形)
    Geo-->>SS: {npc: "Rochor NPC", division: "Central"}

    Note over SS,Gov: Step 2: 拉取 NPC 犯罪数据

    SS->>Gov: GET /api/action/datastore_search<br/>?resource_id=d_5767147db6e5b4c4cfa874db132fef39
    Gov-->>SS: {records: [{npc, year, robbery, snatch_theft,<br/>  housebreaking, outrage_of_modesty,<br/>  theft_of_motor_vehicle}]}

    SS->>Gov: 同时拉取 Unlicensed Moneylending 数据<br/>resource_id=d_b6dc6308d208f668232b4f9e171af3a4
    Gov-->>SS: {records: [{npc, year, uml_cases, harassment}]}

    Note over SS: Step 3: 聚合分析

    SS->>SS: 计算 per-1000-residents 比率<br/>(基于 NPC 辖区人口)
    SS->>SS: 与全国均值对比
    SS->>SS: 生成 0-100 评分

    Note over SS: 评分逻辑:
    Note over SS: housebreaking 权重 35%
    Note over SS: outrage_of_modesty 权重 30%
    Note over SS: robbery + snatch_theft 权重 20%
    Note over SS: theft_of_motor_vehicle 权重 10%
    Note over SS: uml_harassment 权重 5%
```

### 新加坡犯罪类别

| 类别 | 对学生的威胁 | 评分权重 |
|------|-------------|----------|
| Housebreaking (破门行窃) | 🔴 高 | 35% |
| Outrage of Modesty (非礼) | 🔴 高 | 30% |
| Robbery (抢劫) | 🔴 高 | 12% |
| Snatch Theft (抢夺) | 🟠 中高 | 8% |
| Theft of Motor Vehicle (偷车) | 🟢 低 | 10% |
| UML Harassment (非法放贷骚扰) | 🟡 中 | 5% |

### NPC 辖区映射

新加坡 35 个 NPC 的边界需要预加载。来源：
- data.gov.sg NPC 名称列表
- 可能需要手动维护 NPC → Planning Area 的映射表
- 或者用 OneMap API 的 planning area 查询来辅助定位

### 注意事项

- **数据年度更新** — 没有月度粒度，标注年份
- **新加坡整体低犯罪率** — 邻里间差异远小于英国，评分需要更细的区分度
- **NPC 边界 vs 房源坐标** — 需要预加载边界数据做 Point-in-Polygon 判断

---

## 统一评分输出

```
┌──────────────────────────────────────┐
│         SafetyScore 数据结构          │
├──────────────────────────────────────┤
│ safety_score:        78 / 100        │
│ confidence:          "high"          │
│ data_source:         "police.uk"     │
│ data_period:         "2026-04"       │
│                                      │
│ category_breakdown:                  │
│   violent_crime_rate:     8.2/1000   │
│   burglary_rate:          3.1/1000   │
│   robbery_rate:           1.5/1000   │
│   antisocial_rate:        12.4/1000  │
│                                      │
│ comparison:                          │
│   vs_city_avg:           "below"     │
│   vs_city_percentile:    32%         │
│   city_avg_rate:         15.3/1000   │
│                                      │
│ summary:                             │
│   "该区域总体犯罪率低于伦敦均值 20%，  │
│    暴力犯罪率低，入室盗窃率接近均值。  │
│    是 Camden 区内相对安全的街区。"     │
└──────────────────────────────────────┘
```

---

## 缓存策略

```mermaid
graph LR
    Request["评分请求<br/>(lat, lng)"] --> Cache{"Redis 缓存<br/>key: safety:{uk|sg}:{coord_hash}"}
    Cache -->|"命中 (24h 内)"| Return["直接返回"]
    Cache -->|"未命中"| Fetch["调用外部 API"]
    Fetch --> Store["存入 Redis<br/>TTL: 24h (犯罪数据月更)"]
    Store --> Return
```

- 对同一区域的多次查询不会重复调 API
- 缓存 TTL 24 小时足够了（数据月更/年更）
- 超过 API 速率限制时降级使用缓存数据

---

## 对比 Agent 中的使用

安全评分在对比 Agent 中作为**一个独立维度**参与打分和展示：

```
雷达图中: 安全是一条独立的轴
维度表中: 显示各套房的安全评分 + 明细
Trade-off: "C 虽然通勤最差，但安全评分最高 (85 vs A 的 72)"
风险提示: "B 所在区域入室盗窃率高于均值 40%，建议确认门禁情况"
```

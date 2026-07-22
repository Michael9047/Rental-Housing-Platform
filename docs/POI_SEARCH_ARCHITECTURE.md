# POI 周边搜索架构文档

> 房源上传后自动检索周边配套设施，生成配套分析报告与美食聚集地评级。
> 数据源：Google Maps Places API (New)

---

## 一、关键词分层体系

### 1.1 两级分层总览

> **母类** 用于 UI Tab 分组，**子类** 用于实际搜索与数据存储。`gmR` 的 key 均为子类关键词。

| 母类 | 子类 | 搜索端点 |
|------|------|---------|
| **交通** | 地铁站 | searchNearby |
| | 公交站 | searchText 双词 2×2 网格 |
| **医疗** | 医院 | searchNearby |
| | 药店 | searchText 2×2 网格 |
| **购物** | 超市 | searchText 2×2 网格 |
| | 便利店 | searchText 2×2 网格 |
| | 商场 | searchNearby |
| | 酒吧 | searchText 2×2 网格 |
| **美食** | 餐厅 | searchText 2×2 网格 |
| | cafe | searchText 2×2 网格 |
| | 烘焙 | searchText 2×2 网格 |
| | 快餐 | searchText 2×2 网格 |
| | 食阁 | searchText 2×2 网格 |
| **生活** | 市场 | searchText 2×2 网格 |
| | 健身房 | searchText 2×2 网格 |
| **地标** | 小贩中心 | searchText 单矩形 + includedType |

### 1.2 详细检索表

| 母类 | 子类 | 搜索词 | 端点 | 翻页 | 上限 | 备注 |
|------|------|--------|------|------|------|------|
| **交通** | 地铁站 | `["subway_station"]` | searchNearby | — | 20 | 圆形，150m 去重 |
| | 公交站 | `"bus stop"` + `"bus station"` | searchText | 2页 | 320 (双词×2×2格×2页) | 网格分割，80m 去重 |
| **医疗** | 医院 | `["hospital"]` | searchNearby | — | 20 | 圆形，200m 去重 |
| | 药店 | `"pharmacy"` | searchText | 2页 | 160 (2×2格×2页) | 网格分割 |
| **购物** | 超市 | `"supermarket"` | searchText | 2页 | 160 (2×2格×2页) | 网格分割 |
| | 便利店 | `"convenience store"` | searchText | 2页 | 160 (2×2格×2页) | 网格分割 |
| | 商场 | `["shopping_mall"]` | searchNearby | — | 20 | 圆形，150m 去重 |
| | 酒吧 | `"bar"` | searchText | 2页 | 160 (2×2格×2页) | 网格分割 |
| **美食** | 餐厅 | `"restaurant"` | searchText | 3页 | 240 (2×2格×3页) | 网格分割 |
| | cafe | `"cafe"` | searchText | 3页 | 240 (2×2格×3页) | 网格分割 |
| | 烘焙 | `"bakery"` | searchText | 3页 | 240 (2×2格×3页) | 网格分割 |
| | 快餐 | `"fast food"` | searchText | 3页 | 240 (2×2格×3页) | 网格分割 |
| | 食阁 | `"food centre"` | searchText | 3页 | 240 (2×2格×3页) | 网格分割，含小贩中心摊位 |
| **生活** | 市场 | `"market"` | searchText | 2页 | 160 (2×2格×2页) | 网格分割，150m 去重 |
| | 健身房 | `"gym"` | searchText | 2页 | 160 (2×2格×2页) | 网格分割 |
| **地标** | 小贩中心 | `"hawker centre"` + `"food centre"` | searchText | 3页 | 120 (双词×3页，单矩形) | 不走网格，`includedType: "food_court"` 过滤 |

---

## 二、端点与搜索策略

### 2.1 三条执行路径

| 路径 | 关键词数 | 端点 | 搜索形状 | 翻页 | 上限 |
|------|---------|------|---------|------|------|
| **A — searchNearby** | 3（地铁站/商场/医院） | `POST places:searchNearby` | 圆形 circle | 不支持 | 20 |
| **B — 网格 searchText** | 12（其余除小贩中心） | `POST places:searchText` | 矩形 rectangle + 2×2 网格 | L1 美食 3 页 / 其余 2 页 | 160–320 |
| **C — 特殊** | 1（小贩中心） | `POST places:searchText` | 矩形 rectangle + `includedType` | 3 页 × 双词 | 120 |

### 2.2 端点特性对比

| 参数 | searchNearby | searchText |
|------|-------------|------------|
| 请求方式 | `POST places:searchNearby` | `POST places:searchText` |
| 搜索形状 | `circle` (center + radius) | `rectangle` (low + high) |
| 结果上限 | `maxResultCount: 20`（不可翻页） | `pageSize: 20` × N 页（每格） |
| 翻页 | 不支持（不返回 nextPageToken） | L1 美食 3 页 / 其余 2 页 |
| 网格突破 | 不支持 | 2×2 = 4 格 |
| 类型过滤 | `includedTypes` | `includedType`（可选） |
| 文本搜索 | 不支持 | `textQuery` |
| 去重 | 自动（结构化） | 需手动 `place_id` + proximity |

---

## 三、美食质量分层

> 仅对 L1 美食层级的关键词进行评分过滤。Google Places 返回的 `rating` 字段（0-5 分）为评分依据。

| 等级 | 名称 | 评分范围 | 处理方式 |
|------|------|---------|---------|
| **Q1** | 优质 | ≥ 4.4 | 优先展示，聚集分析加权 |
| **Q2** | 标准 | 3.0 — 4.3 | 正常纳入聚集分析 |
| **Q3** | 低质 | < 3.0 | **舍去**，不计入聚集 |

---

## 四、聚集地系统

### 4.1 数据源

| 角色 | 包含关键词 | 说明 |
|------|-----------|------|
| **主 POI** | 餐厅、cafe、烘焙、快餐、食阁 | 聚集计算的核心数据 |
| **附属标签** | 超市、药店、健身房、酒吧、市场 | 300m 内检测，标注于聚集信息中 |

### 4.2 聚类参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 聚类距离 | 150m | Union-Find 并查集，间距 < 150m 归为同一聚集地 |
| 最少店铺 | 3 家 | 不足 3 家不构成有效聚集地 |
| 附属检测半径 | 300m | 检测聚集地周边是否有超市/药店/健身房/酒吧/市场 |

### 4.3 聚集等级

| 等级 | 条件 | 地图颜色 |
|------|------|---------|
| **A** | ≥ 20 家 | 红色 |
| **B** | 8 — 19 家 | 橙色 |
| **C** | 3 — 7 家 | 蓝色 |

### 4.4 命名规则

| 优先级 | 锚点类型 | 检测半径 | 示例 |
|--------|---------|---------|------|
| 1 | 商场 | 250m | "Clementi Mall" |
| 2 | 地铁站 | 400m | "Near Clementi MRT" |
| 3 | 小贩中心 | 200m | "Clementi 448 Market & Food Centre" |
| 4 | 兜底 | — | 聚集地内最常见的 Google vicinity 字段 |

### 4.5 去重规则

| 关键词 | 去重方式 | 阈值 |
|--------|---------|------|
| 地铁站 | proximity | 150m |
| 公交站 | proximity | 80m |
| 医院 | proximity | 200m |
| 商场 | proximity | 150m |
| 市场 | proximity | 150m |
| 全 searchText 关键词 | 同名 + proximity | 50m |

> searchNearby 关键词（地铁站/商场/医院）API 层自动去重；searchText 关键词需手动 post-search 去重。

---

## 五、线路信息（待定）

> 地铁站、公交站的 POI 数据中已预留 `transit_lines` 字段，但 Google Places API 不返回站点线路信息。
> 填充方案待定：

| 方案 | 说明 |
|------|------|
| **LTA DataMall** | 新加坡陆交局官方 API，免费注册，完整站点+线路数据 |
| **静态字典** | Clementi 区域内站点有限，手动建 MRT/LRT 线路索引 |

### 5.1 数据字段（已预留）

```json
{
  "name": "Clementi",
  "keyword": "地铁站",
  "transit_lines": [
    {"name": "East-West Line", "ref": "EW", "vehicle": "subway"}
  ]
}
```

### 5.2 展示（已实现）

- 地图 tooltip：站名下方显示线路 ref
- 列表项：站名旁显示线路编号
- 当前数据为空时不显示

---

## 六、并发控制

| 参数 | 值 |
|------|-----|
| 并发数 | 6 |
| 实现 | Semaphore 队列 |
| 翻页延迟 | 400ms（避免撞 rate limit） |

---

## 七、安全评分

> 新加坡安全评分已接入 data.gov.sg，与 POI 检索合并到同一 Celery 任务异步执行。

### 7.1 新加坡管线

| 参数 | 值 |
|------|-----|
| 数据源 | data.gov.sg — Selected Major Offences by NPC（年度） |
| NPC 映射 | 35 个 NPC 中心坐标，最近邻匹配 |
| 缓存 | 内存 24h（数据年度更新） |
| 存储 | `PropertyPOI.safety_data` JSON 字段 |

### 7.2 评分维度与权重

| 犯罪类别 | 权重 |
|---------|------|
| Housebreaking (破门行窃) | 35% |
| Outrage of Modesty (非礼) | 30% |
| Robbery (抢劫) | 12% |
| Snatch Theft (抢夺) | 8% |
| Motor Theft (偷车) | 10% |
| UML Harassment (非法放贷骚扰) | 5% |

### 7.3 评分公式

```
ratio = zone_weighted_rate / national_weighted_rate
score = clamp(100 - ratio × 50, 10, 100)
```

---

## 八、文件位置

| 文件 | 内容 |
|------|------|
| `frontend/public/poi-compare.html` | 浏览器端验证页面（Google Maps API 直调） |
| `backend/app/services/google_poi_service.py` | **Google Maps 全量 POI 服务**（16 关键词 / 3 路径 / 网格分割） |
| `backend/app/services/safety_scoring.py` | **安全评分服务**（SG: data.gov.sg 已实现 / UK: 待实现） |
| `backend/app/tasks/poi_tasks.py` | Celery 异步任务 — POI + 安全评分合并执行 |
| `backend/app/models/poi.py` | `PropertyPOI` 模型（含 `safety_data` 字段） |
| `backend/app/services/poi_service.py` | 旧 POI 服务（Amap/Overpass，保留向后兼容） |
| `backend/app/services/geocoding_service.py` | 多引擎地理编码（Amap/Google/Overpass/Nominatim） |

### 集成点

| 触发场景 | 调用方式 | 生成数据 |
|---------|---------|---------|
| 房源创建 `POST /api/v1/properties` | `generate_full_poi_for_property.delay(prop.id)` | POI + 安全评分 |
| 房源更新 `PATCH /api/v1/properties/{id}` | 同上 | POI + 安全评分 |
| 批量导入 `POST /api/v1/imports/confirm` | 同上 | POI + 安全评分 |
| 对比 Agent | `comparison_data.gather_comprehensive_metrics()` | 优先读 DB 缓存 |

---

> 最后更新：2026-07-22
> 测试区域：Clementi MRT (1.3153, 103.7648)

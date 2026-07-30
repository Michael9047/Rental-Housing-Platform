# 配套设施词条完善清单

> 编制日期：2026-07-23
> 参考来源：StarRez PMS 数据仓库 schema（Penn 大学）、StarRez 2025 学生满意度调查（418 所机构）、Unite Students（英国最大 PBSA，7 万+床位）、Scape（澳洲/英国）、Yugo（全球 100+ 物业）、UofT Oak House（StarRez PortalX 实例）、PBSA 政府规划指引（英国/澳洲）

---

## 一、现状总览

### 当前架构

```
Institute (公寓)  →  amenities: ARRAY(String(50))   自由文本，无分类
UnitType (户型)   →  amenities: ARRAY(String(50))   自由文本，无分类
Room (房间)       →  无独立 amenities 字段           仅 institute_amenities(Text) 冗余
```

### 核心差距

| 维度 | 行业标准词条数 | 我们已有 | 缺失 |
|------|-------------|--------|------|
| 公寓级 (Institute) | 30 | 14 | 16 |
| 户型级 (UnitType) | 37 | 12 | 25 |
| 房间级 (Room) | 9 | 0 | 9 |
| 服务级 (Services) | 16 | 0 | 16 |
| **合计** | **92** | **26** | **66** |

### 结构性问题

1. **每层内无子分类** — "床"（家具）、"烟雾报警器"（安全）、"包水电"（服务）混在同一数组
2. **无枚举约束** — 中文 "空调" 和英文 "ac" 是同一设施但写法不同
3. **服务维度缺失** — 账单包含、运营服务完全没有建模
4. **房间级字段缺失** — 无法表达同户型不同房间的差异化（楼层、朝向、景观）

---

## 二、目标架构

```
Institute (公寓)
├── building_amenities     ← 楼内公共设施（健身房/自习室/洗衣房…）
├── security_features      ← 安全设施（CCTV/门禁/烟雾报警器…）
├── accessibility_features ← 无障碍设施
└── outdoor_features       ← 户外设施（庭院/屋顶露台/BBQ…）

UnitType (户型)
├── bedroom_furnishings    ← 卧室家具（床型/书桌/衣柜…）
├── bathroom_type          ← 卫浴类型（独立/共用/无障碍）
├── kitchen_appliances     ← 厨房设备（冰箱/微波炉/烤箱…）
├── living_area_items      ← 客厅配置（沙发/茶几/电视…）
├── climate_control        ← 气候控制（空调/暖气）
└── in_unit_laundry        ← 户内洗衣（洗衣机/烘干机）

Room (房间)                ← 需要新 amenities 字段
├── room_attributes        ← 房间属性（楼层/朝向/景观/角房）
├── room_restrictions      ← 房间限制（安静楼层/性别楼层）
└── special_features       ← 特殊配置（阳台/无障碍/宠物友好）

Services (服务)            ← 需要新建模
├── bills_included         ← 账单包含（水/电/网/气/暖气/保险）
├── operational_services   ← 运营服务（前台/维修/保洁/活动）
└── optional_services      ← 增值服务（班车/保洁/床品）
```

---

## 三、词条详细清单

### 优先级说明

- 🔴 **P0 — 核心决策因素**：学生选房第一眼看的信息，缺了影响转化率
- 🟡 **P1 — 竞争力提升**：头部竞争对手标配，加上就有差异化
- 🟢 **P2 — 锦上添花**：高端物业才有，有预算再做

---

## 四、公寓级词条 (Institute Building Amenities)

> 当前模型：`institute.amenities: ARRAY(String(50))`
> 当前拥有：14 个，缺失 16 个

### 4.1 学习与社交空间

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 1 | Study Room / Study Spaces | 自习室 | ✅ `study_room` | — | 所有PBSA |
| 2 | Common Room / Lounge | 公共休息室 | ✅ `common_room` | — | 所有PBSA |
| 3 | **Group Study Room** | 小组讨论室 | ❌ 缺失 | 🟡 P1 | Unite "areas for group work" |
| 4 | **Quiet Room** | 静音室 | ❌ 缺失 | 🟢 P2 | Unite "quiet rooms" |
| 5 | **Games Room** | 游戏室 | ❌ 缺失 | 🟡 P1 | Unite "pool tables, consoles, table tennis" |
| 6 | **Cinema / Movie Room** | 影音室/电影院 | ❌ 缺失 | 🟡 P1 | Unite/Scape/Yugo 标配 |
| 7 | **Multi-faith / Prayer Room** | 多功能室/祈祷室 | ❌ 缺失 | 🟢 P2 | Oak House "Multifaith room" |

### 4.2 运动与健康

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 8 | Gym / Fitness Center | 健身房 | ✅ `gym` | — | 所有PBSA |
| 9 | **Yoga / Meditation Studio** | 瑜伽室/冥想室 | ❌ 缺失 | 🟡 P1 | Unite "yoga studios" |
| 10 | **Swimming Pool** | 泳池 | ⚠️ 数据有映射无 | 🟢 P2 | Scape/Yugo 高端 |
| 11 | **Sports Court** | 球场 | ❌ 缺失 | 🟢 P2 | Unite "sports courts" |

### 4.3 生活便利

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 12 | Laundry Room | 洗衣房 | ✅ `laundry` | — | StarRez #2 |
| 13 | Bike Storage | 自行车存放 | ✅ `bike_storage` | — | 所有PBSA |
| 14 | Parking | 停车位 | ✅ `parking` | — | 所有PBSA |
| 15 | Mail Room | 邮件室 | ✅ `mail_room` | — | 所有PBSA |
| 16 | Elevator / Lift | 电梯 | ✅ `elevator` | — | 多楼层标配 |
| 17 | **Package Lockers** | 快递柜/包裹柜 | ❌ 缺失 | 🔴 P0 | StarRez #6 满意度驱动 |
| 18 | **Dining Hall** | 食堂/餐厅 | ❌ 缺失 | 🟡 P1 | Oak House "on-site dining hall" |
| 19 | **Vending Machine** | 自动售货机 | ❌ 缺失 | 🟢 P2 | Unite |
| 20 | **Co-working Space** | 共享办公空间 | ❌ 缺失 | 🟡 P1 | Scape/Yugo 后疫情趋势 |

### 4.4 户外空间

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 21 | Garden / Courtyard | 花园/庭院 | ✅ `garden` | — | 所有PBSA |
| 22 | **Rooftop Terrace** | 屋顶露台 | ❌ 缺失 | 🟡 P1 | Unite/Scape/Yugo 新公寓标配 |
| 23 | **BBQ Area** | 烧烤区 | ⚠️ 数据有映射无 | 🟢 P2 | Scape |
| 24 | **Balcony (Building)** | 公共阳台 | ✅ `balcony` | — | 部分物业 |

### 4.5 安全设施 🆕 建议独立子分类

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 25 | CCTV | 视频监控 | ✅ `security` | — | 所有PBSA |
| 26 | **Key Card / Fob Access** | 电子门禁/刷卡进入 | ❌ 缺失 | 🔴 P0 | Oak House "secured building with fob access" |
| 27 | **24/7 Security Staff** | 24小时安保人员 | ❌ 缺失 | 🔴 P0 | Unite/Oak House |
| 28 | **Smoke Detector** | 烟雾报警器 | ❌ 缺失 | 🔴 P0 | PBSA 法规要求 |
| 29 | **Fire Alarm System** | 火警系统 | ❌ 缺失 | 🔴 P0 | PBSA 法规要求 |
| 30 | **CO Detector** | 一氧化碳报警器 | ❌ 缺失 | 🔴 P0 | 英国法规要求 |
| 31 | **Video Intercom** | 视频对讲 | ❌ 缺失 | 🟢 P2 | 高端公寓 |
| 32 | **Visitor Check-in** | 访客登记 | ❌ 缺失 | 🟢 P2 | StarRez Front Desk 模块 |

### 4.6 无障碍设施 🆕 新子分类

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 33 | **Wheelchair Accessible** | 轮椅通道 | ❌ 缺失 | 🔴 P0 | 法规 + Scape/Unite |
| 34 | **Accessible Elevator** | 无障碍电梯 | ❌ 缺失 | 🔴 P0 | 法规 |
| 35 | **Accessible Bathroom** | 无障碍卫生间 | ❌ 缺失 | 🔴 P0 | 法规 |
| 36 | **Guide Dog Friendly** | 导盲犬友好 | ❌ 缺失 | 🟡 P1 | 英国法规 |
| 37 | **Accessible Parking** | 无障碍车位 | ❌ 缺失 | 🟡 P1 | 法规 |

> 公寓级小计：现有 14 ❯ 建议 37（新增 23）

---

## 五、户型级词条 (UnitType Amenities)

> 当前模型：`unit_type.amenities: ARRAY(String(50))`
> 当前拥有：12 个，缺失 25 个

### 5.1 卧室家具

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 1 | **Bed — Single** | 单人床 | ❌ 缺失 | 🔴 P0 | Unite/Scape 标准床型 |
| 2 | **Bed — ¾ / Double** | 双人床/中床 | ❌ 缺失 | 🔴 P0 | Unite "comfortable double/¾ bed" |
| 3 | **Bed — King Single** | 加大单人床 | ❌ 缺失 | 🟡 P1 | Scape/Yugo |
| 4 | **Bed — XL Twin** | 加长单人床 | ❌ 缺失 | 🟡 P1 | StarRez/Lindenwood "Extra-long twin" |
| 5 | **Bed — Bunk** | 上下铺 | ❌ 缺失 | 🟢 P2 | Kings Island/StarRez "bunk bed style" |
| 6 | Desk | 书桌 | ⚠️ `desk` 映射有数据未用 | 🔴 P0 | 所有PBSA 标配 |
| 7 | Chair | 椅子 | ❌ 缺失 | 🔴 P0 | 所有PBSA 标配 |
| 8 | **Wardrobe / Closet** | 衣柜 | ❌ 缺失 | 🔴 P0 | 所有PBSA 标配 |
| 9 | **Dresser / Drawers** | 抽屉柜/五斗柜 | ❌ 缺失 | 🔴 P0 | Lindenwood "dresser" / Oak House "drawers under bed" |
| 10 | **Bedside Table** | 床头柜 | ❌ 缺失 | 🟡 P1 | Unite/Scape "bedside table" |
| 11 | **Bookshelf / Shelves** | 书架/置物架 | ❌ 缺失 | 🟢 P2 | Scape |
| 12 | **Curtains / Blinds** | 窗帘/百叶窗 | ❌ 缺失 | 🟡 P1 | Unite 标配 |
| 13 | **Noticeboard / Pinboard** | 布告板 | ❌ 缺失 | 🟢 P2 | Unite |
| 14 | **Wall Mirror** | 墙面镜 | ❌ 缺失 | 🟢 P2 | Unite/Scape |
| 15 | **Under-bed Storage** | 床下储物空间 | ❌ 缺失 | 🟡 P1 | Unite/Scape |
| 16 | **Desk Lamp** | 台灯 | ❌ 缺失 | 🟢 P2 | Scape |
| 17 | Furnished | 家具齐全 | ✅ `furnished` | — | 行业通用标识 |

### 5.2 卫浴类型

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 18 | En-suite Bathroom | 独立卫浴 | ✅ `ensuite` | — | 核心房型区分 |
| 19 | Shared Bathroom | 共用卫浴 | ✅ `shared_bathroom` | — | 核心房型区分 |
| 20 | **Towel Rail** | 毛巾架 | ❌ 缺失 | 🟢 P2 | Unite/Scape |
| 21 | **Shower (not bath)** | 淋浴(无浴缸) | ❌ 缺失 | 🟢 P2 | 常见区分 |

### 5.3 厨房设备 🆕 建议独立子数组

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 22 | Private Kitchen / Kitchenette | 独立厨房 | ✅ `kitchen` / `kitchenette` | — | Studio 标配 |
| 23 | Shared Kitchen | 共用厨房 | ✅ `shared_kitchen` | — | En-suite 套间 |
| 24 | **Fridge / Freezer** | 冰箱/冰柜 | ❌ 缺失 | 🔴 P0 | Unite/Scape 厨房标配 |
| 25 | **Microwave** | 微波炉 | ❌ 缺失 | 🔴 P0 | Unite/Scape 厨房标配 |
| 26 | **Oven / Hob / Cooktop** | 烤箱/灶台 | ❌ 缺失 | 🔴 P0 | Unite/Scape 厨房标配 |
| 27 | **Dishwasher** | 洗碗机 | ❌ 缺失 | 🟢 P2 | Scape 高端户型 |
| 28 | **Kettle** | 烧水壶 | ❌ 缺失 | 🟡 P1 | Unite 标配（英国刚需） |
| 29 | **Toaster** | 烤面包机 | ❌ 缺失 | 🟡 P1 | Unite 标配 |
| 30 | **Cookware / Cutlery** | 厨具/餐具 | ❌ 缺失 | 🟢 P2 | Scape |

### 5.4 客厅配置（多人套间）

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 31 | **Dining Table + Chairs** | 餐桌+椅子 | ❌ 缺失 | 🔴 P0 | Unite "dining table with chairs" |
| 32 | **Sofa / Couch** | 沙发 | ❌ 缺失 | 🔴 P0 | Unite/Scape 多人套间标配 |
| 33 | **Coffee Table** | 茶几 | ❌ 缺失 | 🟡 P1 | Scape/Yugo |
| 34 | TV | 电视 | ✅ `tv` | — | Scape "flat-screen TV" |
| 35 | **Vacuum Cleaner** | 吸尘器 | ❌ 缺失 | 🟢 P2 | Unite 套间标配 |

### 5.5 电器与气候

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 36 | Air Conditioning | 空调 | ✅ `ac` | — | 热带/亚热带必需 |
| 37 | Heating | 暖气 | ✅ `heating` | — | 英国/北美必需 |
| 38 | **Iron + Ironing Board** | 熨斗+烫衣板 | ❌ 缺失 | 🟢 P2 | Unite/Scape |
| 39 | **USB Outlets** | USB插座 | ❌ 缺失 | 🟢 P2 | 新公寓趋势 |

### 5.6 户内洗衣

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 40 | **In-unit Washer** | 户内洗衣机 | ❌ 缺失 | 🟡 P1 | Scape 高端 studio |
| 41 | **In-unit Dryer** | 户内烘干机 | ❌ 缺失 | 🟡 P1 | Scape 高端 studio |

### 5.7 户型限制

| # | 行业标准名 (en) | 推荐中文名 | 当前字段 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 42 | **Female Only** | 仅限女性 | ⚠️ `female_only` 在 Room/Institute层 | 🟡 P1 | 常见于英国/中东市场 |
| 43 | **Couples Allowed** | 允许情侣入住 | ⚠️ `couples_allowed` 在 Institute 层 | 🟡 P1 | 部分公寓 |
| 44 | **No Smoking** | 禁止吸烟 | ❌ 缺失 | 🟡 P1 | 行业标配规则 |

> 户型级小计：现有 12 ❯ 建议 44（新增 32）

---

## 六、房间级词条 (Room Attributes) 🆕 新字段

> 当前状况：Room 模型无独立 amenities，仅 `institute_amenities: Text` 冗余字段
> 建议：新增 `room_attributes: ARRAY(String(30))` 或 JSONB 字段

| # | 行业标准名 (en) | 推荐中文名 | 类型建议 | 优先级 | 来源 |
|---|---------------|-----------|---------|--------|------|
| 1 | **Floor Level** | 所在楼层 | Integer (已有 `floor`) | 🔴 P0 | StarRez schema |
| 2 | **Building Block / Wing** | 楼栋/翼楼 | String (已有 `building_block`) | 🟡 P1 | Oak House "Premium vs Standard" |
| 3 | **Room View** | 房间景观 | Enum: city/garden/sea/pool/courtyard | 🔴 P0 | Scape "large window with view" |
| 4 | **Room Orientation** | 朝向 | Enum: north/south/east/west | 🟡 P1 | 华人市场刚需 |
| 5 | **Corner Room** | 边户/角房 | Boolean | 🟡 P1 | 溢价因素 |
| 6 | **High Floor** | 高楼层 | Boolean | 🟡 P1 | 溢价因素 |
| 7 | **Quiet Room** | 安静房间（远离电梯/马路） | Boolean | 🟢 P2 | UW Hansee "24-hour quiet hours" |
| 8 | **Balcony Room** | 带阳台 | Boolean | 🔴 P0 | Scape/Yugo 溢价 |
| 9 | **Accessible Room** | 无障碍房间 | Boolean | 🔴 P0 | Unite/Scape |
| 10 | **Pet Friendly Room** | 可养宠物 | Boolean | 🟢 P2 | UW Radford Court |
| 11 | **Newly Renovated** | 新装修 | Boolean | 🟡 P1 | 常见卖点 |
| 12 | **Room Size** | 房间面积（区别于户型平均面积） | Decimal | 🟢 P2 | 部分物业有同户型大小差异 |

> 房间级小计：现有 0 ❯ 建议 12（全部新增）

---

## 七、服务层词条 (Services) 🆕 新维度

> 当前状况：完全未建模，散落在描述文本和 amenity 数组里
> 建议：需要独立的数据结构（独立表或 JSONB 字段），不作为 amenity 数组的一部分

### 7.1 账单包含 (Bills Included)

| # | 行业标准名 (en) | 推荐中文名 | 类型 | 优先级 | 来源 |
|---|---------------|-----------|------|--------|------|
| 1 | **Water Included** | 包水费 | Boolean | 🔴 P0 | Unite 核心卖点 |
| 2 | **Electricity Included** | 包电费 | Boolean | 🔴 P0 | Unite 核心卖点 |
| 3 | **Gas Included** | 包燃气 | Boolean | 🔴 P0 | 英国必需 |
| 4 | **Heating Included** | 包暖气 | Boolean | 🔴 P0 | 英国必需 |
| 5 | **Wi-Fi / Internet Included** | 包网费 | Boolean | 🔴 P0 | StarRez #1 满意度驱动 |
| 6 | **Contents Insurance Included** | 包财产险 | Boolean | 🟡 P1 | Unite "Endsleigh insurance" 标配 |
| 7 | **TV Licence Included** | 包电视牌照费 | Boolean | 🟢 P2 | 英国特殊 |
| 8 | **Council Tax Included** | 包市政税 | Boolean | 🟡 P1 | 英国学生豁免场景 |

### 7.2 运营服务 (Operational Services)

| # | 行业标准名 (en) | 推荐中文名 | 类型 | 优先级 | 来源 |
|---|---------------|-----------|------|--------|------|
| 9 | **24/7 On-site Team** | 24/7 现场团队 | Boolean | 🔴 P0 | Unite "24/7 staff on site, 365 days" |
| 10 | **Free Maintenance** | 免费维修 | Boolean | 🔴 P0 | 所有PBSA |
| 11 | **Communal Area Cleaning** | 公区保洁 | Boolean | 🟡 P1 | 所有PBSA |
| 12 | **Room Cleaning Service** | 房间保洁 | Boolean / Frequency | 🟢 P2 | Scape 高端 / Yugo "bi-weekly housekeeping" |
| 13 | **Social Events Program** | 社交活动 | Boolean | 🟡 P1 | Unite/Oak House "community dinners, museum visits, fitness classes" |
| 14 | **Resident App** | 住户 App | Boolean | 🟡 P1 | Unite "MyUnite App" |
| 15 | **On-site Maintenance Team** | 驻场维修团队 | Boolean | 🟡 P1 | Unite |
| 16 | **Multilingual Staff** | 多语言工作人员 | Boolean | 🟡 P1 | Yugo（国际学生市场） |

### 7.3 增值服务 (Optional / Premium Services)

| # | 行业标准名 (en) | 推荐中文名 | 类型 | 优先级 | 来源 |
|---|---------------|-----------|------|--------|------|
| 17 | **Airport Pickup** | 接机服务 | Boolean | 🟢 P2 | 国际学生市场 |
| 18 | **Linen / Bedding Pack** | 床品包（付费） | Boolean | 🟢 P2 | Scape "towels and bed linen provided" |
| 19 | **Kitchen Starter Pack** | 厨房入门包 | Boolean | 🟢 P2 | 部分公寓 |
| 20 | **Shuttle Bus** | 班车/接驳车 | Boolean | 🟡 P1 | Yugo "free transportation to universities" |
| 21 | **Bike Rental** | 自行车租赁 | Boolean | 🟢 P2 | 部分公寓 |
| 22 | **Printing Service** | 打印服务 | Boolean | 🟢 P2 | Unite 部分物业 |
| 23 | **Storage Service** | 假期行李寄存 | Boolean | 🟡 P1 | Unite "limited secure storage" |
| 24 | **Short-term / Flexible Lease** | 灵活租期/短租 | Boolean | 🟡 P1 | Unite "41-51 weeks" / 部分公寓 |

> 服务级小计：现有 0 ❯ 建议 24（全部新增）

---

## 八、完整优先级排序（实施建议）

### 🔴 P0 — 第一轮必做（核心决策因素，直接影响转化率）

| 序号 | 所属层级 | 词条 | 理由 |
|------|---------|------|------|
| 1 | 户型级 | 床型（Single/Double/King Single） | 学生第一关注点 |
| 2 | 户型级 | 书桌 + 椅子 | 所有PBSA标配，我们没有 |
| 3 | 户型级 | 衣柜 | 所有PBSA标配，我们没有 |
| 4 | 户型级 | 抽屉柜 | 所有PBSA标配，我们没有 |
| 5 | 户型级 | 冰箱/冰柜 | 厨房标配，不能只说"有厨房" |
| 6 | 户型级 | 微波炉 | 厨房标配 |
| 7 | 户型级 | 烤箱/灶台 | 厨房标配 |
| 8 | 户型级 | 餐桌+椅子 | 多人套间标配 |
| 9 | 户型级 | 沙发 | 多人套间标配 |
| 10 | 公寓级 | 快递柜 | StarRez #6 满意度驱动 |
| 11 | 公寓级 | 电子门禁/刷卡 | Oak House 标配，比"24小时门禁"精确 |
| 12 | 公寓级 | 24小时安保人员 | 家长决策关键信息 |
| 13 | 公寓级 | 烟雾报警器 + 火警系统 | 安全合规 |
| 14 | 公寓级 | 轮椅通道 + 无障碍卫浴 | 法规合规 |
| 15 | 房间级 | 是否带阳台 | 溢价核心因素 |
| 16 | 房间级 | 景观类型 | 溢价核心因素 |
| 17 | 房间级 | 是否无障碍房间 | 法规合规 |
| 18 | 服务级 | 包水/电/网/暖气 | 决策关键信息 |
| 19 | 服务级 | 24/7 现场团队 | 所有PBSA标配 |
| 20 | 服务级 | 免费维修 | 所有PBSA标配 |

**P0 合计：20 个词条**

### 🟡 P1 — 第二轮（提升竞争力，头部竞争对手标配）

| 序号 | 所属层级 | 词条 |
|------|---------|------|
| 21 | 公寓级 | 游戏室 |
| 22 | 公寓级 | 影音室 |
| 23 | 公寓级 | 瑜伽/冥想室 |
| 24 | 公寓级 | 屋顶露台 |
| 25 | 公寓级 | 共享办公空间 |
| 26 | 公寓级 | 食堂/餐厅 |
| 27 | 户型级 | King Single / XL Twin 床型 |
| 28 | 户型级 | 床头柜 |
| 29 | 户型级 | 窗帘 |
| 30 | 户型级 | 床下储物 |
| 31 | 户型级 | 烧水壶 |
| 32 | 户型级 | 烤面包机 |
| 33 | 户型级 | 茶几 |
| 34 | 户型级 | 户内洗衣机/烘干机 |
| 35 | 户型级 | Female Only / Couples Allowed |
| 36 | 房间级 | 楼栋/翼楼 |
| 37 | 房间级 | 朝向 |
| 38 | 房间级 | 边户/高楼层 |
| 39 | 房间级 | 新装修 |
| 40 | 服务级 | 包财产险 |
| 41 | 服务级 | 公区保洁 |
| 42 | 服务级 | 社交活动 |
| 43 | 服务级 | 住户App |
| 44 | 服务级 | 多语言员工 |
| 45 | 服务级 | 班车/接驳 |
| 46 | 服务级 | 假期行李寄存 |
| 47 | 服务级 | 灵活租期 |

**P1 合计：27 个词条**

### 🟢 P2 — 第三轮（高端差异化，有预算/需求时做）

| 序号 | 所属层级 | 词条 |
|------|---------|------|
| 48 | 公寓级 | 静音室 |
| 49 | 公寓级 | 多功能信仰室 |
| 50 | 公寓级 | 泳池 |
| 51 | 公寓级 | 球场 |
| 52 | 公寓级 | BBQ区 |
| 53 | 公寓级 | 自动售货机 |
| 54 | 公寓级 | 视频对讲 |
| 55 | 公寓级 | 访客登记 |
| 56 | 户型级 | 上下铺 |
| 57 | 户型级 | 书架 |
| 58 | 户型级 | 布告板 |
| 59 | 户型级 | 墙面镜 |
| 60 | 户型级 | 台灯 |
| 61 | 户型级 | 毛巾架 |
| 62 | 户型级 | 淋浴/浴缸区分 |
| 63 | 户型级 | 洗碗机 |
| 64 | 户型级 | 厨具/餐具 |
| 65 | 户型级 | 吸尘器 |
| 66 | 户型级 | 熨斗+烫衣板 |
| 67 | 户型级 | USB插座 |
| 68 | 房间级 | 安静房间 |
| 69 | 房间级 | 宠物友好 |
| 70 | 房间级 | 面积差异 |
| 71 | 服务级 | 房间保洁 |
| 72 | 服务级 | 接机 |
| 73 | 服务级 | 床品包 |
| 74 | 服务级 | 厨房入门包 |
| 75 | 服务级 | 自行车租赁 |
| 76 | 服务级 | 打印服务 |
| 77 | 服务级 | 电视牌照费 |

**P2 合计：30 个词条**

---

## 九、服务层设计建议

当前服务信息散落在各处，建议后续独立建模：

### 方案 A：JSONB 字段（轻量，推荐先试行）

```python
# 在 Institute 或 UnitType 上新增
service_inclusions: JSONB = {
    "bills": {
        "water": True,
        "electricity": True,
        "gas": False,
        "heating": True,
        "wifi": True,
        "insurance": False
    },
    "operations": {
        "onsite_team_247": True,
        "maintenance_free": True,
        "communal_cleaning": True,
        "social_events": False,
        "resident_app": False
    },
    "optional": ["airport_pickup", "linen_pack", "storage"]
}
```

### 方案 B：独立 ServiceProfile 表（重型，适合有 PMS 对接需求时）

```python
class ServiceProfile(Base):
    institute_id: FK
    water_included: bool
    electricity_included: bool
    gas_included: bool
    heating_included: bool
    wifi_included: bool
    insurance_included: bool
    onsite_team_247: bool
    maintenance_free: bool
    communal_cleaning: bool
    room_cleaning: Optional[str]  # "none" / "weekly" / "biweekly"
    social_events: bool
    shuttle_bus: bool
    flexible_lease: bool
    # ...
```

**建议：先用方案 A 在 `institute` 上加一个 `service_inclusions` JSONB 字段跑起来，后续根据 PMS 对接需求决定是否升级到方案 B。**

---

## 十、参考资料

| 来源 | 类型 | 链接 |
|------|------|------|
| StarRez 官网 | PMS 产品 | https://www.starrez.com/ |
| StarRez 2025 学生满意度调查 | 行业报告 | 418 所机构参与 |
| Unite Students 设施页面 | PBSA 运营商 | https://www.unitestudents.com/about-us/facilities-amenities |
| UofT Oak House (StarRez PortalX) | 真实物业 | utoronto.starrezhousing.com |
| Penn 大学 StarRez 数据仓库 | 数据库 Schema | provider.www.upenn.edu — dwstarrez.room_type |
| Scape 物业页面 | PBSA 运营商 | scape.com.au |
| Yugo 物业页面 | PBSA 运营商 | yugo.com |
| Lindenwood University StarRez Portal | 真实物业 | lindenwood.edu/starrez |
| PBSA 政府规划指引 (UK/WA) | 法规标准 | 英国 Edinburgh 2030 / WA Draft Position Statement 2025 |

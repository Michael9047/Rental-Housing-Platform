# -*- coding: utf-8 -*-
"""
四市场真实租房种子脚本 v2 — Property（公寓楼）+ RoomType（房型）层级结构

与 v1 的关键区别：
  - v1: 每套房源是一个独立的 Property（3195 条扁平记录）
  - v2: 一个 Property = 一栋公寓楼/小区，内含 2-5 个 RoomType（Studio/Ensuite/1Bed/2Bed/...）

数据来源：
  - 新加坡: data.gov.sg HDB 租金交易，按 town 聚合
  - 伦敦:   Inside Airbnb listings.csv，按 neighbourhood 聚合
  - 美国:   Kaggle 10州房屋数据，按 city 聚合
  - 香港:   基于真实市场行情的手工构建数据（5所大学周边大厦/小区）

运行方式：
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_v2_properties.py
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_v2_properties.py --dry-run
  cd backend && .venv/Scripts/python.exe scripts/seed/seed_v2_properties.py --clear-existing
"""

import asyncio, csv, os, random, sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, delete
from app.db.session import async_session_maker
from app.models.property import Property, PropertyType, PropertyStatus, RentType, DepositType
from app.models.property_image import PropertyImage
from app.models.room_type import RoomType, RoomTypeEnum, RoomTypeStatus, DepositType as RTDepositType
from app.models.user import User

DATA_DIR = Path(__file__).resolve().parent / "data"

# ═══════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════

TARGET_PER_MARKET = 100  # 每个市场 100 套 Property

ROOM_TYPE_TEMPLATES = {
    "studio": {
        "names": ["Studio 单人套间", "单人Studio", "精装Studio"],
        "room_type": RoomTypeEnum.studio, "bedrooms": 1, "bathrooms": 1,
        "area_range": (18, 30), "price_factor": 0.70, "available_count": (1, 5),
    },
    "ensuite": {
        "names": ["Ensuite 独卫套间", "Ensuite 单人套间", "精装Ensuite"],
        "room_type": RoomTypeEnum.ensuite, "bedrooms": 1, "bathrooms": 1,
        "area_range": (25, 40), "price_factor": 0.85, "available_count": (2, 8),
    },
    "one_bed": {
        "names": ["一室一厅", "一室一厅精装", "一室一厅高层"],
        "room_type": RoomTypeEnum.one_bed, "bedrooms": 1, "bathrooms": 1,
        "area_range": (35, 55), "price_factor": 1.00, "available_count": (1, 4),
    },
    "two_bed": {
        "names": ["两室一厅", "两室一厅精装", "两室两卫"],
        "room_type": RoomTypeEnum.two_bed, "bedrooms": 2, "bathrooms": 1,
        "area_range": (55, 80), "price_factor": 1.40, "available_count": (1, 3),
    },
    "three_bed_plus": {
        "names": ["三室两卫", "三室两卫豪华", "三室一厅大户型"],
        "room_type": RoomTypeEnum.three_bed_plus, "bedrooms": 3, "bathrooms": 2,
        "area_range": (80, 110), "price_factor": 2.00, "available_count": (1, 2),
    },
    "shared": {
        "names": ["合租单间", "单间合租", "温馨单间"],
        "room_type": RoomTypeEnum.shared, "bedrooms": 1, "bathrooms": 1,
        "area_range": (8, 18), "price_factor": 0.40, "available_count": (1, 3),
    },
}

# 每个 Property 的房型组合（随机选择一个组合）
ROOM_TYPE_COMBOS = [
    # (房型配置列表)
    # Studio 为主的公寓楼
    [("studio", 1.0), ("ensuite", 1.15), ("one_bed", 1.0)],
    [("studio", 1.0), ("studio", 0.9), ("ensuite", 1.0), ("one_bed", 1.0)],
    # Ensuite 为主的公寓楼
    [("ensuite", 1.0), ("one_bed", 1.0), ("two_bed", 1.0)],
    [("ensuite", 1.0), ("ensuite", 0.9), ("one_bed", 1.0), ("two_bed", 1.0), ("shared", 1.0)],
    [("studio", 1.0), ("ensuite", 1.0), ("one_bed", 1.0), ("two_bed", 1.0)],
    # 多房型公寓
    [("ensuite", 1.0), ("one_bed", 1.0), ("two_bed", 1.0), ("three_bed_plus", 1.0)],
    [("studio", 1.0), ("ensuite", 1.0), ("one_bed", 1.0), ("two_bed", 1.0), ("three_bed_plus", 1.0)],
    # 偏大户型
    [("one_bed", 1.0), ("two_bed", 1.0), ("three_bed_plus", 1.0)],
    [("two_bed", 1.0), ("two_bed", 0.95), ("three_bed_plus", 1.0)],
    # 合租为主
    [("shared", 1.0), ("shared", 0.9), ("studio", 1.0), ("ensuite", 1.0)],
    [("shared", 1.0), ("ensuite", 1.0), ("one_bed", 1.0)],
    # 简单组合
    [("studio", 1.0), ("one_bed", 1.0)],
    [("ensuite", 1.0), ("two_bed", 1.0)],
    [("one_bed", 1.0), ("two_bed", 1.0), ("shared", 1.0)],
]


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════

def safe_int(val, default=0):
    try: return int(float(val))
    except: return default

def safe_float(val, default=0.0):
    try: return float(val)
    except: return default

def safe_str(val, default=""):
    if val is None or (isinstance(val, float) and val != val): return default
    return str(val).strip()

def rdate(start=14, end=120):
    return date.today() + timedelta(days=random.randint(start, end))

def jitter(lat, lon, m=300):
    o = m / 111000 * random.uniform(-1, 1)
    return (round(lat + o, 6), round(lon + o * random.uniform(-1, 1), 6))

def pick_combo():
    return random.choice(ROOM_TYPE_COMBOS)

def make_room_types(base_price_cny, property_area_sqm):
    """为一个 Property 生成 RoomType 列表"""
    combo = pick_combo()
    room_types = []
    for rt_key, price_mult in combo:
        tpl = ROOM_TYPE_TEMPLATES[rt_key]
        name = random.choice(tpl["names"])
        area = Decimal(random.randint(*tpl["area_range"]))
        price = Decimal(int(base_price_cny * tpl["price_factor"] * price_mult))
        avail = random.randint(*tpl["available_count"])
        # 每种房型的配套设施（模拟公寓管理方填写）
        amenity_map = {
            "studio":  [["独立卫浴", "独立厨房", "WiFi", "空调", "家具齐全", "书桌"],
                        ["独立卫浴", "独立厨房", "WiFi", "空调", "家具齐全", "洗衣机"],
                        ["独立卫浴", "独立厨房", "WiFi", "空调", "家具齐全", "冰箱", "微波炉"]],
            "ensuite":  [["独立卫浴", "共享厨房", "WiFi", "空调", "家具齐全", "书桌"],
                        ["独立卫浴", "共享厨房", "WiFi", "空调", "家具齐全", "衣柜"],
                        ["独立卫浴", "共享厨房", "WiFi", "空调", "家具齐全", "书桌", "台灯"]],
            "one_bed":  [["独立卫浴", "独立厨房", "WiFi", "空调", "全屋家电", "阳台"],
                        ["独立卫浴", "独立厨房", "WiFi", "空调", "全屋家电", "沙发", "阳台"],
                        ["独立卫浴", "独立厨房", "WiFi", "空调", "洗衣机", "冰箱", "衣柜"]],
            "two_bed":  [["独立卫浴", "独立厨房", "WiFi", "空调", "全屋家电", "阳台"],
                        ["独立卫浴", "独立厨房", "WiFi", "中央空调", "全屋家电", "阳台", "沙发"],
                        ["独立卫浴", "独立厨房", "WiFi", "空调", "洗衣机", "冰箱", "衣柜", "阳台"]],
            "three_bed_plus": [["独立卫浴", "独立厨房", "WiFi", "中央空调", "全屋家电", "阳台", "储物间"],
                               ["独立卫浴", "独立厨房", "WiFi", "中央空调", "全屋家电", "双阳台", "储物间"],
                               ["两卫", "独立厨房", "WiFi", "中央空调", "全屋家电", "阳台", "储物间", "衣帽间"]],
            "shared":   [["公共卫浴", "共享厨房", "WiFi", "空调", "家具齐全", "书桌"],
                        ["公共卫浴", "共享厨房", "WiFi", "空调", "家具齐全", "衣柜", "台灯"],
                        ["公共卫浴", "共享厨房", "WiFi", "空调", "床垫", "书桌", "椅子"]],
        }
        amenities = random.choice(amenity_map.get(rt_key, amenity_map["ensuite"]))
        room_types.append(dict(
            name=name, room_type=tpl["room_type"],
            bedrooms=tpl["bedrooms"], bathrooms=tpl["bathrooms"],
            price_monthly=price, area_sqm=area,
            available_count=avail,
            available_from=rdate(),
            min_stay_months=random.choice([3, 6, 12]),
            deposit_amount=int(price),
            deposit_type=random.choice([RTDepositType.one_month, RTDepositType.two_month]),
            amenities=amenities,
            description=f"{name}，面积约{area}㎡，月租CNY{price}。",
            status=RoomTypeStatus.available,
        ))
    return room_types


# ═══════════════════════════════════════════════
# 🇸🇬 新加坡 — HDB 数据聚合为公寓楼
# ═══════════════════════════════════════════════

SG_TOWNS = {
    "CLEMENTI": "金文泰", "QUEENSTOWN": "女皇镇", "BUKIT TIMAH": "武吉知马",
    "BUKIT MERAH": "红山", "JURONG EAST": "裕廊东", "JURONG WEST": "裕廊西",
}
SG_ESTATE_NAMES = [
    "Clementi Woods", "West Coast Plaza", "The Clement Canopy", "Clementi Park",
    "West Cove", "Hundred Trees", "Blue Horizon", "Clementi Gateway",
    "Queenstown Tower", "The Stirling", "Queens Peak", "Commonwealth Towers",
    "Dawson Vista", "SkyVille", "SkyTerrace", "Forfar Heights",
    "Bukit Timah Plaza", "The Cascadia", "Maple Woods", "Spring Grove",
    "Bukit Merah Central", "Telok Blangah Tower", "Henderson Wave",
    "Jurong East Point", "Westgate Tower", "J Gateway", "The Centris",
    "Jurong West Central", "Pioneer Mall", "Boon Lay Garden",
]
SG_BUILDING_PREFIXES = ["", "The ", "", "The ", "", "The ", ""]

def load_sg_properties(target=100):
    """从 HDB CSV 加载，按 town 聚合为公寓楼"""
    fpath = DATA_DIR / "sg_hdb_rentals_transactions_basic.csv"
    if not fpath.exists():
        print("[SG] 数据文件不存在，将使用手工数据")
        return _gen_sg_handmade(target)

    # 读取并分组
    by_town: dict[str, list[dict]] = {}
    with open(fpath, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            town = row.get("town", "").upper()
            if town not in SG_TOWNS:
                continue
            if safe_int(row.get("year", 0)) < 2024:
                continue
            mr = safe_int(row.get("monthly_rent", 0))
            if mr <= 0:
                continue
            by_town.setdefault(town, []).append(row)

    total = sum(len(v) for v in by_town.values())
    print(f"[SG] HDB 2024-2026 有效记录: {total} 条，分布在 {len(by_town)} 个 town")

    # 每个 town 按比例分配 Property 数量
    props = []
    for town, rows in by_town.items():
        n = max(5, int(target * len(rows) / total))
        tc = SG_TOWNS[town]

        # 聚合：取该 town 的租金中位数作为基准价
        rents = sorted(safe_int(r.get("monthly_rent", 0)) for r in rows)
        median_rent_sgd = rents[len(rents) // 2]

        for i in range(n):
            estate = SG_ESTATE_NAMES[(hash(f"{town}_{i}") % len(SG_ESTATE_NAMES))]
            bldg = f"{tc}·{estate} 公寓"

            # 取一条记录的坐标做 jitter
            ref = rows[i % len(rows)]
            lat, lon = None, None
            if ref.get("lat") and ref.get("lon"):
                lat, lon = jitter(safe_float(ref.get("lat")), safe_float(ref.get("lon")), 500)

            price_cny = int(median_rent_sgd * 5.3)
            props.append(dict(
                title=f"{bldg}"[:200],
                description=f"{tc}精装学生公寓「{estate}」，近NUS工学院。配备泳池/健身房/自习室/24小时安保。步行可达超市和食阁。",
                address=f"{estate}, {tc}, Singapore",
                district=f"新加坡-{tc}", country="SG",
                price_monthly=Decimal(price_cny),
                area_sqm=Decimal(random.randint(80, 200)),
                bedrooms=0, bathrooms=0,  # Property 层级不再有意义
                property_type=PropertyType.apartment,
                latitude=Decimal(str(lat)) if lat else None,
                longitude=Decimal(str(lon)) if lon else None,
                deposit_amount=median_rent_sgd, deposit_type=DepositType.one_month,
                amenities=["泳池", "健身房", "自习室", "24小时安保", "近地铁", "近超市"],
                available_from=rdate(), min_stay_months=3,
                min_lease_months=random.choice([3, 6, 12]),
                max_lease_months=random.choice([12, 24, 36, 60]),
                floor=random.randint(3, 30), room_number="",
                institute_id=2,  # NUS
                _base_rent_sgd=median_rent_sgd,  # 临时字段，不入库
            ))
    print(f"[SG] 生成 {len(props)} 个公寓楼")
    return props


def _gen_sg_handmade(target=100):
    """手工生成新加坡公寓楼（CSV 不可用时的备用方案）"""
    props = []
    tc_list = list(SG_TOWNS.values())
    for i in range(target):
        tc = tc_list[i % len(tc_list)]
        estate = SG_ESTATE_NAMES[i % len(SG_ESTATE_NAMES)]
        base_rent = random.choice([2000, 2500, 3000, 3500, 4000, 4500, 5000])
        price_cny = int(base_rent * 5.3)
        lat, lon = jitter(1.31, 103.77, 3000)
        props.append(dict(
            title=f"{estate} 公寓"[:200],
            description=f"{tc}精装学生公寓「{estate}」，近NUS。设施齐全，交通便利。",
            address=f"{estate}, {tc}, Singapore",
            district=f"新加坡-{tc}", country="SG",
            price_monthly=Decimal(price_cny),
            area_sqm=Decimal(random.randint(80, 200)),
            bedrooms=0, bathrooms=0,
            property_type=PropertyType.apartment,
            latitude=Decimal(str(lat)), longitude=Decimal(str(lon)),
            deposit_amount=base_rent, deposit_type=DepositType.one_month,
            amenities=["泳池", "健身房", "自习室", "WiFi", "近地铁"],
            available_from=rdate(), min_stay_months=3,
            min_lease_months=random.choice([3, 6, 12]),
            max_lease_months=random.choice([12, 24, 36]),
            floor=random.randint(3, 30), room_number="",
            institute_id=2,
            _base_rent_sgd=base_rent,
        ))
    print(f"[SG] 手工生成 {len(props)} 个公寓楼")
    return props


# ═══════════════════════════════════════════════
# 🇬🇧 伦敦 — Airbnb 数据聚合为公寓楼
# ═══════════════════════════════════════════════

UK_NH = {
    "Westminster": "威斯敏斯特", "Kensington and Chelsea": "肯辛顿/切尔西",
    "Hammersmith and Fulham": "哈默史密斯", "Wandsworth": "旺兹沃思",
    "Lambeth": "兰贝斯", "Southwark": "南华克", "Tower Hamlets": "塔村区",
    "Hackney": "哈克尼", "Islington": "伊斯灵顿", "Camden": "卡姆登",
    "Greenwich": "格林威治", "Newham": "纽汉", "Haringey": "哈林盖",
    "Brent": "布伦特", "Ealing": "伊灵", "Hounslow": "豪恩斯洛",
}
UK_ESTATE_NAMES = [
    "Victoria Plaza", "Kensington Court", "Chelsea Harbour", "The Imperial",
    "Thames View", "Canary Wharf Tower", "London Bridge Place", "The Westminster",
    "Hyde Park Gate", "Regent's Court", "Bloomsbury House", "King's Cross Central",
    "Shoreditch Lofts", "Angel Court", "Camden Lock", "Hammersmith Grove",
    "Battersea Reach", "Vauxhall Tower", "Greenwich Peninsula", "Royal Victoria",
    "Stratford Heights", "Wembley Park", "Richmond Riverside", "Islington Square",
    "Bermondsey Works", "Aldgate East", "Whitechapel Place", "Earl's Court",
    "Notting Hill Gate", "Bayswater Mansion",
]

def load_uk_properties(target=100):
    """从 Airbnb CSV 加载，按 neighbourhood 聚合"""
    fpath = DATA_DIR / "london_airbnb_listings.csv"
    if not fpath.exists():
        print("[UK] 数据文件不存在，将使用手工数据")
        return _gen_uk_handmade(target)

    by_nh: dict[str, list[dict]] = {}
    with open(fpath, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            p = safe_float(safe_str(row.get("price", "0")).replace("$", "").replace(",", ""))
            if p < 20 or p > 500:
                continue
            if safe_int(row.get("minimum_nights", 999)) > 90:
                continue
            if safe_int(row.get("availability_365", 0)) <= 0:
                continue
            nb = safe_str(row.get("neighbourhood", ""))
            if nb not in UK_NH:
                continue
            by_nh.setdefault(nb, []).append(row)

    total = sum(len(v) for v in by_nh.values())
    print(f"[UK] Airbnb 有效记录: {total} 条，分布在 {len(by_nh)} 个 neighbourhood")

    props = []
    for nb, rows in by_nh.items():
        n = max(3, int(target * len(rows) / total))
        nc = UK_NH[nb]

        nightly_prices = [safe_float(safe_str(r.get("price", "0")).replace("$", "").replace(",", "")) for r in rows]
        median_nightly = sorted(nightly_prices)[len(nightly_prices) // 2]
        median_monthly = int(median_nightly * 25)
        price_cny = int(median_monthly * 9.1)

        for i in range(n):
            estate = UK_ESTATE_NAMES[(hash(f"{nb}_{i}") % len(UK_ESTATE_NAMES))]
            bldg = f"{nc}·{estate}"

            ref = rows[i % len(rows)]
            lat, lon = None, None
            if ref.get("latitude") and ref.get("longitude"):
                lat, lon = jitter(safe_float(ref.get("latitude")), safe_float(ref.get("longitude")), 300)

            props.append(dict(
                title=f"{estate} 学生公寓"[:200],
                description=f"伦敦{nc}「{estate}」学生公寓，近University of London。精装公寓楼，配备暖气/WiFi/洗衣房/24小时安保。周边超市/餐厅/地铁站齐全。",
                address=f"{estate}, {nc}, London",
                district=f"伦敦-{nc}", country="GB",
                price_monthly=Decimal(price_cny),
                area_sqm=Decimal(random.randint(60, 180)),
                bedrooms=0, bathrooms=0,
                property_type=PropertyType.apartment,
                latitude=Decimal(str(lat)) if lat else None,
                longitude=Decimal(str(lon)) if lon else None,
                deposit_amount=median_monthly, deposit_type=DepositType.one_month,
                amenities=["WiFi", "暖气", "洗衣房", "24小时安保", "近地铁"],
                available_from=rdate(), min_stay_months=1,
                min_lease_months=random.choice([1, 3, 6]),
                max_lease_months=random.choice([6, 12, 24]),
                floor=random.randint(0, 15), room_number="",
                institute_id=None,
                _base_rent_gbp=median_monthly,
            ))
    print(f"[UK] 生成 {len(props)} 个公寓楼")
    return props


def _gen_uk_handmade(target=100):
    """手工生成伦敦公寓楼"""
    props = []
    nc_list = list(UK_NH.values())
    for i in range(target):
        nc = nc_list[i % len(nc_list)]
        estate = UK_ESTATE_NAMES[i % len(UK_ESTATE_NAMES)]
        base_rent = random.choice([600, 800, 1000, 1200, 1500, 1800, 2000])
        price_cny = int(base_rent * 9.1)
        lat, lon = jitter(51.51, -0.13, 5000)
        props.append(dict(
            title=f"伦敦{nc}·{estate} 学生公寓"[:200],
            description=f"伦敦{nc}「{estate}」学生公寓，精装公寓楼。",
            address=f"{estate}, {nc}, London",
            district=f"伦敦-{nc}", country="GB",
            price_monthly=Decimal(price_cny),
            area_sqm=Decimal(random.randint(60, 180)),
            bedrooms=0, bathrooms=0,
            property_type=PropertyType.apartment,
            latitude=Decimal(str(lat)), longitude=Decimal(str(lon)),
            deposit_amount=base_rent, deposit_type=DepositType.one_month,
            amenities=["WiFi", "暖气", "洗衣房", "24小时安保"],
            available_from=rdate(), min_stay_months=1,
            min_lease_months=random.choice([1, 3, 6]),
            max_lease_months=random.choice([6, 12, 24]),
            floor=random.randint(0, 15), room_number="",
            institute_id=None,
            _base_rent_gbp=base_rent,
        ))
    print(f"[UK] 手工生成 {len(props)} 个公寓楼")
    return props


# ═══════════════════════════════════════════════
# 🇺🇸 美国 — House 数据聚合为公寓楼
# ═══════════════════════════════════════════════

US_CITY = {
    "Los Angeles": (34.05, -118.24), "San Francisco": (37.77, -122.42),
    "San Diego": (32.72, -117.16), "San Jose": (37.34, -121.89),
    "New York": (40.71, -74.01), "Chicago": (41.88, -87.63),
    "Seattle": (47.61, -122.33), "Miami": (25.76, -80.19),
    "Orlando": (28.54, -81.38), "Tampa": (27.95, -82.46),
    "Phoenix": (33.45, -112.07), "Tucson": (32.22, -110.97),
    "Charlotte": (35.23, -80.84), "Raleigh": (35.78, -78.64),
    "Birmingham": (33.52, -86.80), "Huntsville": (34.73, -86.59),
    "New Orleans": (29.95, -90.07), "Baton Rouge": (30.45, -91.19),
    "Columbia": (34.00, -81.03), "Charleston": (32.78, -79.93),
}
US_ESTATE_NAMES = [
    "University Tower", "College Park", "The Varsity", "Campus Edge",
    "The Collegiate", "University Commons", "Scholar's Place", "Ivy Ridge",
    "Campus View", "The Graduate", "Academic Village", "College Square",
    "The Forum", "University Heights", "Scholar's Gate", "Campus Corner",
    "The Study", "College Terrace", "The Dean", "Alumni House",
    "University Place", "Campus Lodge", "The Academy", "Scholar's Walk",
]


def load_us_properties(target=100):
    """从 US houses CSV 加载，按 city 聚合"""
    fpath = DATA_DIR / "us_houses_cleaned.csv"
    if not fpath.exists():
        print("[US] 数据文件不存在，将使用手工数据")
        return _gen_us_handmade(target)

    by_city: dict[str, list[dict]] = {}
    with open(fpath, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            price = safe_int(row.get("price_num", 0))
            if price < 50000 or price > 5000000:
                continue
            city = safe_str(row.get("city", ""))
            if city not in US_CITY:
                continue
            by_city.setdefault(city, []).append(row)

    total = sum(len(v) for v in by_city.values())
    print(f"[US] 有效记录: {total} 条，分布在 {len(by_city)} 个城市")

    # 取前 N 个城市
    city_counts = sorted(by_city.items(), key=lambda x: len(x[1]), reverse=True)
    top_cities = city_counts[:20]
    city_total = sum(len(rows) for _, rows in top_cities)

    props = []
    for city_name, rows in top_cities:
        n = max(3, int(target * len(rows) / city_total))
        lat0, lon0 = US_CITY[city_name]

        sale_prices = [safe_int(r.get("price_num", 300000)) for r in rows]
        median_sale = sorted(sale_prices)[len(sale_prices) // 2]
        monthly_rent = int(median_sale * 0.005)
        price_cny = int(monthly_rent * 7.2)

        for i in range(n):
            estate = US_ESTATE_NAMES[(hash(f"{city_name}_{i}") % len(US_ESTATE_NAMES))]
            lat, lon = jitter(lat0, lon0, 3000)

            props.append(dict(
                title=f"{estate} 学生公寓"[:200],
                description=f"{city_name}「{estate}」学生公寓，精装公寓楼。配备空调/WiFi/健身房/洗衣房/停车位。近大学城，生活便利。",
                address=f"{estate}, {city_name}, US",
                district=f"美国-{city_name}", country="US",
                price_monthly=Decimal(price_cny),
                area_sqm=Decimal(random.randint(60, 200)),
                bedrooms=0, bathrooms=0,
                property_type=PropertyType.apartment,
                latitude=Decimal(str(lat)), longitude=Decimal(str(lon)),
                deposit_amount=monthly_rent, deposit_type=DepositType.one_month,
                amenities=["空调", "WiFi", "健身房", "洗衣房", "停车位", "泳池"],
                available_from=rdate(), min_stay_months=3,
                min_lease_months=random.choice([6, 12]),
                max_lease_months=random.choice([12, 24, 36]),
                floor=random.randint(2, 20), room_number="",
                institute_id=None,
                _base_rent_usd=monthly_rent,
            ))
    print(f"[US] 生成 {len(props)} 个公寓楼")
    return props


def _gen_us_handmade(target=100):
    """手工生成美国公寓楼"""
    props = []
    city_list = list(US_CITY.keys())
    for i in range(target):
        city = city_list[i % len(city_list)]
        lat0, lon0 = US_CITY[city]
        estate = US_ESTATE_NAMES[i % len(US_ESTATE_NAMES)]
        base_rent = random.choice([500, 800, 1000, 1200, 1500, 1800, 2200])
        price_cny = int(base_rent * 7.2)
        lat, lon = jitter(lat0, lon0, 3000)
        props.append(dict(
            title=f"美国{city}·{estate} 学生公寓"[:200],
            description=f"{city}「{estate}」学生公寓，精装公寓楼。",
            address=f"{estate}, {city}, US",
            district=f"美国-{city}", country="US",
            price_monthly=Decimal(price_cny),
            area_sqm=Decimal(random.randint(60, 200)),
            bedrooms=0, bathrooms=0,
            property_type=PropertyType.apartment,
            latitude=Decimal(str(lat)), longitude=Decimal(str(lon)),
            deposit_amount=base_rent, deposit_type=DepositType.one_month,
            amenities=["空调", "WiFi", "健身房", "停车位"],
            available_from=rdate(), min_stay_months=3,
            min_lease_months=random.choice([6, 12]),
            max_lease_months=random.choice([12, 24, 36]),
            floor=random.randint(2, 20), room_number="",
            institute_id=None,
            _base_rent_usd=base_rent,
        ))
    print(f"[US] 手工生成 {len(props)} 个公寓楼")
    return props


# ═══════════════════════════════════════════════
# 🇭🇰 香港 — 手工构建大厦/小区
# ═══════════════════════════════════════════════

HK_BUILDINGS = [
    # ── HKU 周边 ──
    dict(name="均益大厦", area="西环", lat=22.2845, lon=114.1372, desc="西环干诺道西，步行5分钟到HKU东闸。高层海景，全新装修。"),
    dict(name="泓都", area="坚尼地城", lat=22.2820, lon=114.1335, desc="坚尼地城新海旁高档私人屋苑，步行3分钟到HKU医学院。会所设施齐全。"),
    dict(name="缙城峰", area="西营盘", lat=22.2858, lon=114.1430, desc="西营盘第一街高档住宅，步行8分钟到HKU。全新装修配名牌家电。"),
    dict(name="翰林峰", area="石塘咀", lat=22.2865, lon=114.1400, desc="石塘咀皇后大道西新楼，步行5分钟到HKU。独立厨卫。"),
    dict(name="五福大厦", area="坚尼地城", lat=22.2815, lon=114.1320, desc="坚尼地城卑路乍街，步行6分钟到HKU。高层海景。"),
    dict(name="观龙楼", area="西环", lat=22.2800, lon=114.1300, desc="西环坚尼地城龙华街公共屋邨，步行12分钟到HKU工学院。"),
    dict(name="学士台", area="薄扶林", lat=22.2830, lon=114.1380, desc="薄扶林道，步行3分钟到HKU东闸。学生首选居住地。"),
    dict(name="高乐花园", area="西营盘", lat=22.2870, lon=114.1440, desc="西营盘高街，步行10分钟到HKU。安静社区。"),
    dict(name="帝后华庭", area="西环", lat=22.2875, lon=114.1410, desc="西环皇后大道西，步行8分钟到HKU。新楼精装。"),
    dict(name="宝翠园", area="薄扶林", lat=22.2810, lon=114.1360, desc="薄扶林道大型私人屋苑，步行7分钟到HKU。会所设施齐全。"),
    dict(name="海怡半岛", area="香港仔", lat=22.2480, lon=114.1500, desc="香港仔大型屋苑，巴士15分钟到HKU。海景单位。"),
    dict(name="南湾", area="鸭脷洲", lat=22.2420, lon=114.1520, desc="鸭脷洲高档住宅，巴士20分钟到HKU。豪华会所。"),
    dict(name="贝沙湾", area="薄扶林", lat=22.2650, lon=114.1330, desc="数码港旁豪宅，巴士15分钟到HKU。无敌海景。"),
    dict(name="置富花园", area="薄扶林", lat=22.2600, lon=114.1350, desc="薄扶林大型屋苑，巴士10分钟到HKU。环境清幽。"),
    dict(name="华富邨", area="薄扶林", lat=22.2550, lon=114.1370, desc="薄扶林公共屋邨，巴士15分钟到HKU。性价比高。"),

    # ── CUHK 周边 ──
    dict(name="第一城", area="沙田", lat=22.3860, lon=114.2030, desc="沙田第一城，东铁线大学站两站即达CUHK。大型私人屋苑。"),
    dict(name="伟华中心", area="沙田", lat=22.3820, lon=114.1890, desc="沙田市中心，东铁线沙田站步行3分钟。楼下新城市广场。"),
    dict(name="新港城", area="马鞍山", lat=22.4210, lon=114.2320, desc="马鞍山大型私人屋苑，高层海景。泳池/健身房/商场齐全。"),
    dict(name="海日湾", area="大埔", lat=22.4280, lon=114.2050, desc="大埔白石角新楼，近香港科学园。海景+山景，会所设施顶级。"),
    dict(name="大埔中心", area="大埔", lat=22.4500, lon=114.1680, desc="大埔市中心，楼下大埔超级城。东铁线/巴士直达CUHK。"),
    dict(name="运头塘村", area="大埔", lat=22.4450, lon=114.1650, desc="大埔公共屋邨，巴士15分钟到CUHK医学院。实惠之选。"),
    dict(name="河畔花园", area="沙田", lat=22.3840, lon=114.1970, desc="沙田城门河畔，安静社区。河畔步道可跑步/骑行。"),
    dict(name="银禧花园", area="沙田", lat=22.3900, lon=114.1980, desc="沙田火炭，东铁线直达CUHK。清静住宅区。"),
    dict(name="骏景园", area="沙田", lat=22.4000, lon=114.1950, desc="沙田火炭大型私人屋苑，东铁线直达CUHK。花园式社区。"),
    dict(name="鹿茵山庄", area="大埔", lat=22.4350, lon=114.1750, desc="大埔半山豪宅，巴士到CUHK。低密度花园社区。"),
    dict(name="太湖花园", area="大埔", lat=22.4520, lon=114.1700, desc="大埔市中心私人屋苑，巴士15分钟到CUHK。配套成熟。"),
    dict(name="岚山", area="大埔", lat=22.4450, lon=114.1550, desc="大埔新楼，环境清幽。适合CUHK研究生/教职员。"),

    # ── HKUST 周边 ──
    dict(name="蔚蓝湾畔", area="将军澳", lat=22.3150, lon=114.2650, desc="将军澳坑口站上盖，小巴11M直达HKUST。会所设施齐全。"),
    dict(name="新都城", area="将军澳", lat=22.3220, lon=114.2570, desc="将军澳宝琳站上盖，小巴12号直达HKUST。楼下大型商场。"),
    dict(name="都会駅", area="将军澳", lat=22.3070, lon=114.2520, desc="将军澳调景岭站上盖，海景新楼。高端会所。"),
    dict(name="南丰广场", area="将军澳", lat=22.3160, lon=114.2640, desc="将军澳坑口，小巴11M直达HKUST。楼下商场/超市/戏院。"),
    dict(name="将军澳中心", area="将军澳", lat=22.3120, lon=114.2600, desc="将军澳市中心大型屋苑，交通方便。HKUST学生最多居住区。"),
    dict(name="东港城", area="将军澳", lat=22.3160, lon=114.2670, desc="将军澳坑口大型私人屋苑，地铁上盖。HKUST首选。"),
    dict(name="维景湾畔", area="将军澳", lat=22.3100, lon=114.2580, desc="将军澳调景岭，海景单位。地铁/小巴直达HKUST。"),
    dict(name="清水湾半岛", area="清水湾", lat=22.3200, lon=114.2750, desc="清水湾低密度住宅，近HKUST校园。海景清幽。"),

    # ── CityU/BU 周边 ──
    dict(name="又一村", area="九龙塘", lat=22.3340, lon=114.1760, desc="九龙塘低密度豪宅区，步行8分钟到CityU。环境清幽。"),
    dict(name="爱海颂", area="深水埗", lat=22.3300, lon=114.1600, desc="深水埗新楼，地铁10分钟到CityU。高层海景。"),
    dict(name="星河明居", area="钻石山", lat=22.3410, lon=114.2020, desc="钻石山站上盖，地铁两站到九龙塘。高层山景。"),
    dict(name="南山邨", area="石硖尾", lat=22.3330, lon=114.1720, desc="石硖尾公共屋邨，步行10分钟到CityU。预算首选。"),
    dict(name="又一居", area="九龙塘", lat=22.3350, lon=114.1770, desc="九龙塘大型私人屋苑，步行10分钟到CityU/BU。社区高尚。"),
    dict(name="碧海蓝天", area="深水埗", lat=22.3320, lon=114.1580, desc="深水埗新楼群，地铁8分钟到CityU。海景单位。"),
    dict(name="升悦居", area="深水埗", lat=22.3310, lon=114.1590, desc="深水埗私人屋苑，地铁到CityU方便。配套成熟。"),

    # ── PolyU 周边 ──
    dict(name="海滨南岸", area="红磡", lat=22.3030, lon=114.1840, desc="红磡海滨，步行5分钟到PolyU。高层海景。高端会所。"),
    dict(name="黄埔花园", area="红磡", lat=22.3050, lon=114.1900, desc="红磡黄埔大型屋苑，步行8分钟到PolyU。社区成熟。"),
    dict(name="红磡湾中心", area="红磡", lat=22.3080, lon=114.1860, desc="红磡湾中心，步行10分钟到PolyU。小区安静有花园。"),
    dict(name="天铸", area="何文田", lat=22.3140, lon=114.1810, desc="何文田站上盖豪宅新楼，地铁一站到红磡。Miele家电配会所。"),
    dict(name="翔龙湾", area="土瓜湾", lat=22.3150, lon=114.1900, desc="土瓜湾新楼，巴士10分钟到PolyU。高层海景。"),
    dict(name="海逸豪园", area="红磡", lat=22.3070, lon=114.1920, desc="红磡海滨大型屋苑，步行可达PolyU。海景/泳池/会所。"),
    dict(name="半岛豪庭", area="红磡", lat=22.3060, lon=114.1850, desc="红磡站旁新楼，步行5分钟到PolyU。高级住宅。"),
    dict(name="都会轩", area="尖沙咀", lat=22.2980, lon=114.1730, desc="尖沙咀东，地铁+步行12分钟到PolyU。高档住宅。"),

    # ── 港岛东 (通勤方便) ──
    dict(name="康怡花园", area="太古", lat=22.2840, lon=114.2170, desc="太古站上盖大型屋苑，地铁20分钟到中环/HKU。"),
    dict(name="城市花园", area="北角", lat=22.2910, lon=114.2000, desc="北角大型私人屋苑，地铁15分钟到HKU。配套齐全。"),
    dict(name="康山花园", area="鰂鱼涌", lat=22.2860, lon=114.2130, desc="鰂鱼涌私人屋苑，地铁18分钟到HKU。高层山景。"),
    dict(name="太古城", area="太古", lat=22.2860, lon=114.2190, desc="太古站上盖超大型屋苑，港岛最大私人住宅区。地铁直达中环。"),
    dict(name="鲤景湾", area="西湾河", lat=22.2850, lon=114.2240, desc="西湾河海滨屋苑，地铁25分钟到HKU。海景+安静社区。"),
    dict(name="杏花邨", area="杏花邨", lat=22.2780, lon=114.2400, desc="港岛东大型私人屋苑，地铁+巴士35分钟到HKU。花园式社区。"),
    dict(name="新翠花园", area="柴湾", lat=22.2650, lon=114.2400, desc="柴湾私人屋苑，地铁30分钟到HKU（一程直达）。超实惠。"),
    dict(name="形荟", area="筲箕湾", lat=22.2780, lon=114.2290, desc="筲箕湾新楼，地铁到港岛各校方便。智能家居配全屋家电。"),
    dict(name="蓝湾半岛", area="小西湾", lat=22.2630, lon=114.2500, desc="小西湾大型屋苑，巴士到港岛各校。海景+超实惠。"),
    dict(name="嘉亨湾", area="西湾河", lat=22.2860, lon=114.2230, desc="西湾河海滨新楼，高层海景。地铁站步行3分钟。"),
]

# HK 大学 institute_id 映射
HK_INSTITUTES = {
    "HKU": 1, "CUHK": 2, "HKUST": 3, "CityU": 4, "BU": 5, "PolyU": 6,
}

def load_hk_properties(target=100):
    """手工构建香港公寓楼，按大厦/小区分组"""
    # 如果目标数量超过已有列表，循环复用但微调名称
    buildings = []
    for i in range(target):
        base = HK_BUILDINGS[i % len(HK_BUILDINGS)]
        if i < len(HK_BUILDINGS):
            buildings.append(base)
        else:
            # 复用并加编号后缀
            b = base.copy()
            suffix = chr(ord('A') + (i // len(HK_BUILDINGS)))
            b["name"] = f"{b['name']}-{suffix}座"
            buildings.append(b)

    # 分配 institute
    for i, b in enumerate(buildings):
        if "HKU" in b["desc"] or "西环" in b["area"] or "坚尼地城" in b["area"] or "西营盘" in b["area"] or "薄扶林" in b["area"] or "石塘咀" in b["area"]:
            b["institute_id"] = None  # 暂无 HKU institute
            b["near_uni"] = "HKU"
        elif "CUHK" in b["desc"] or "沙田" in b["area"] or "大埔" in b["area"] or "马鞍山" in b["area"]:
            b["institute_id"] = None
            b["near_uni"] = "CUHK"
        elif "HKUST" in b["desc"] or "将军澳" in b["area"] or "清水湾" in b["area"]:
            b["institute_id"] = None
            b["near_uni"] = "HKUST"
        elif "CityU" in b["desc"] or "BU" in b["desc"] or "九龙塘" in b["area"] or "深水埗" in b["area"] or "石硖尾" in b["area"] or "钻石山" in b["area"]:
            b["institute_id"] = None
            b["near_uni"] = "CityU/BU"
        elif "PolyU" in b["desc"] or "红磡" in b["area"] or "何文田" in b["area"] or "土瓜湾" in b["area"] or "尖沙咀" in b["area"]:
            b["institute_id"] = None
            b["near_uni"] = "PolyU"
        else:
            b["institute_id"] = None
            b["near_uni"] = "港岛各校"

    props = []
    for b in buildings:
        # 香港基价 HKD → CNY × 0.92
        base_rent_hkd = random.choice([8000, 10000, 12000, 15000, 18000, 22000, 28000, 35000])
        price_cny = int(base_rent_hkd * 0.92)
        lat, lon = jitter(b["lat"], b["lon"], 200)

        props.append(dict(
            title=f"{b['name']}"[:200],
            description=f"香港{b['area']}{b['name']}，近{b['near_uni']}。{b['desc']}。月租約HKD{base_rent_hkd}（约CNY{price_cny}）。",
            address=f"香港{b['area']}{b['name']}",
            district=f"香港-{b['area']}", country="HK",
            price_monthly=Decimal(price_cny),
            area_sqm=Decimal(random.randint(50, 150)),
            bedrooms=0, bathrooms=0,
            property_type=PropertyType.apartment,
            latitude=Decimal(str(lat)), longitude=Decimal(str(lon)),
            deposit_amount=base_rent_hkd, deposit_type=DepositType.one_month,
            amenities=random.choice([
                ["空调", "WiFi", "近地铁"],
                ["空调", "WiFi", "泳池", "健身房"],
                ["空调", "WiFi", "家具齐全", "近地铁"],
                ["空调", "WiFi", "海景", "会所"],
                ["空调", "WiFi", "新装修", "家具齐全"],
            ]),
            available_from=rdate(), min_stay_months=random.choice([3, 6, 12]),
            min_lease_months=random.choice([3, 6, 12]),
            max_lease_months=random.choice([12, 24, 36]),
            floor=random.randint(3, 40), room_number="",
            institute_id=b.get("institute_id"),
            _base_rent_hkd=base_rent_hkd,
        ))

    print(f"[HK] 生成 {len(props)} 个公寓楼")
    return props


# ═══════════════════════════════════════════════
# 种子写入
# ═══════════════════════════════════════════════

async def seed_v2(dry_run=False, clear_existing=False):
    """主函数"""

    # ── 生成各市场数据 ──
    random.seed(42)  # 可复现
    sg_props = load_sg_properties(TARGET_PER_MARKET)
    random.seed(43)
    uk_props = load_uk_properties(TARGET_PER_MARKET)
    random.seed(44)
    us_props = load_us_properties(TARGET_PER_MARKET)
    random.seed(45)
    hk_props = load_hk_properties(TARGET_PER_MARKET)

    all_props = sg_props + uk_props + us_props + hk_props
    print(f"\n[总计] {len(all_props)} 个公寓楼待处理")

    if dry_run:
        print("\n=== DRY RUN MODE ===\n")
        from collections import Counter
        cnt = Counter(p["country"] for p in all_props)
        for country, n in sorted(cnt.items()):
            print(f"  {country}: {n} 个公寓楼")
            sample = [p for p in all_props if p["country"] == country]
            for p in sample[:3]:
                rts = make_room_types(int(p["price_monthly"]), int(p.get("area_sqm", 100)))
                print(f"    - {p['title'][:60]}")
                print(f"      RoomTypes: {len(rts)} 个")
                for rt in rts:
                    print(f"        {rt['name']}: CNY{rt['price_monthly']}/月, {rt['area_sqm']}㎡, 可租{rt['available_count']}间")
        total_rts = sum(len(make_room_types(int(p["price_monthly"]), int(p.get("area_sqm", 100)))) for p in all_props)
        print(f"\n[DRY RUN] Property: {len(all_props)} → RoomType: ~{total_rts}")
        return

    # ── 数据库操作 ──
    async with async_session_maker() as session:
        # 获取房东列表
        result = await session.execute(
            select(User).where(User.role == "landlord").limit(50)
        )
        landlords = result.scalars().all()
        if not landlords:
            print("[ERROR] 没有房东账号！")
            return
        lids = [l.id for l in landlords]
        print(f"房东: {[(l.id, l.username) for l in landlords[:5]]}{'...' if len(landlords) > 5 else ''}\n")

        if clear_existing:
            print("=== 清除旧数据 ===\n")
            # 先删 room_types（FK 依赖 properties）
            dr = await session.execute(delete(RoomType))
            print(f"[CLEAR] room_types: {dr.rowcount}")
            # 再删 property_images
            dr = await session.execute(delete(PropertyImage))
            print(f"[CLEAR] property_images: {dr.rowcount}")
            # 最后删 properties
            dr = await session.execute(delete(Property))
            print(f"[CLEAR] properties: {dr.rowcount}")
            await session.flush()
            print()

        # ── 写入 ──
        prop_count = 0
        rt_count = 0
        for i, pdata in enumerate(all_props):
            # 创建 Property
            prop = Property(
                landlord_id=lids[i % len(lids)],
                status=PropertyStatus.available,
                rent_type=RentType.monthly,
                title=pdata["title"],
                description=pdata.get("description", ""),
                address=pdata["address"],
                district=pdata["district"],
                country=pdata["country"],
                price_monthly=pdata["price_monthly"],
                area_sqm=pdata.get("area_sqm"),
                bedrooms=pdata.get("bedrooms", 0),
                bathrooms=pdata.get("bathrooms", 0),
                property_type=pdata["property_type"],
                latitude=pdata.get("latitude"),
                longitude=pdata.get("longitude"),
                deposit_amount=pdata.get("deposit_amount", 1000),
                deposit_type=pdata.get("deposit_type"),
                amenities=pdata.get("amenities"),
                available_from=pdata.get("available_from"),
                min_stay_months=pdata.get("min_stay_months", 3),
                min_lease_months=pdata.get("min_lease_months", 12),
                max_lease_months=pdata.get("max_lease_months", 60),
                floor=pdata.get("floor"),
                room_number=pdata.get("room_number", ""),
                institute_id=pdata.get("institute_id"),
                service_fee_rate=0.10,
            )
            session.add(prop)
            await session.flush()  # 获取 prop.id

            # 创建 RoomTypes
            base_price = int(pdata["price_monthly"])
            area = int(pdata.get("area_sqm", 100))
            random.seed(prop.id)  # 每个 Property 的房型可复现
            room_types = make_room_types(base_price, area)

            for rt_data in room_types:
                rt = RoomType(
                    property_id=prop.id,
                    name=rt_data["name"],
                    room_type=rt_data["room_type"],
                    bedrooms=rt_data["bedrooms"],
                    bathrooms=rt_data["bathrooms"],
                    price_monthly=rt_data["price_monthly"],
                    area_sqm=rt_data["area_sqm"],
                    available_count=rt_data["available_count"],
                    available_from=rt_data["available_from"],
                    min_stay_months=rt_data["min_stay_months"],
                    deposit_amount=rt_data["deposit_amount"],
                    deposit_type=rt_data["deposit_type"],
                    amenities=rt_data["amenities"],
                    description=rt_data["description"],
                    status=rt_data["status"],
                )
                session.add(rt)
                rt_count += 1

            # 根据 RoomType 更新 Property 的 bedrooms/bathrooms（取最大值）
            prop.bedrooms = max(rt_data["bedrooms"] for rt_data in room_types)
            prop.bathrooms = max(rt_data["bathrooms"] for rt_data in room_types)
            # price_monthly 更新为最低房型价格（展示用起始价）
            prop.price_monthly = min(rt_data["price_monthly"] for rt_data in room_types)

            prop_count += 1
            if prop_count % 100 == 0:
                print(f"  [{prop_count:04d}] {prop_count} Properties, {rt_count} RoomTypes ...")
                await session.flush()

        await session.commit()

        from collections import Counter
        cnt = Counter(p["country"] for p in all_props)
        parts = " + ".join(f"{k}={v}" for k, v in sorted(cnt.items()))
        print(f"\n{'='*60}")
        print(f"[DONE] {parts} = {prop_count} 个公寓楼, {rt_count} 个房型")
        print(f"{'='*60}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    clear = "--clear-existing" in sys.argv
    asyncio.run(seed_v2(dry_run=dry, clear_existing=clear))

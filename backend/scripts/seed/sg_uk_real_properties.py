# -*- coding: utf-8 -*-
"""
新加坡 HDB & 英国伦敦 Airbnb 真实租房数据种子脚本

数据来源：
  - 新加坡: data.gov.sg — HDB 租金交易记录 (2021-2026)，含精确经纬度
  - 伦敦:   Inside Airbnb — listings.csv (2025-03)，含精确经纬度

运行方式：
  cd backend && .venv/Scripts/python.exe scripts/seed/sg_uk_real_properties.py
  cd backend && .venv/Scripts/python.exe scripts/seed/sg_uk_real_properties.py --dry-run
  cd backend && .venv/Scripts/python.exe scripts/seed/sg_uk_real_properties.py --clear-existing
  cd backend && .venv/Scripts/python.exe scripts/seed/sg_uk_real_properties.py --sg-only
  cd backend && .venv/Scripts/python.exe scripts/seed/sg_uk_real_properties.py --uk-only
"""

import asyncio
import csv
import os
import random
import sys
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
from app.models.property import (
    Property, PropertyType, PropertyStatus, RentType, DepositType,
)
from app.models.user import User

DATA_DIR = Path(__file__).resolve().parent / "data"
SG_CSV = DATA_DIR / "sg_hdb_rentals_transactions_basic.csv"
UK_CSV = DATA_DIR / "london_airbnb_listings.csv"


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════

def safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_str(val: Any, default: str = "") -> str:
    if val is None or (isinstance(val, float) and val != val):
        return default
    return str(val).strip()


def random_date_in_range(start_days: int = 14, end_days: int = 120) -> date:
    days = random.randint(start_days, end_days)
    return date.today() + timedelta(days=days)


def jitter_coord(lat: float, lon: float, radius_m: float = 300) -> tuple[float, float]:
    offset = radius_m / 111000 * random.uniform(-1, 1)
    return (round(lat + offset, 6), round(lon + offset * random.uniform(-1, 1), 6))


# ═══════════════════════════════════════════════
# 新加坡 — 常量 & 映射
# ═══════════════════════════════════════════════

SG_NUS_TOWNS = {
    "CLEMENTI", "QUEENSTOWN", "BUKIT TIMAH", "BUKIT MERAH",
    "JURONG EAST", "JURONG WEST",
}

SG_FLAT_BEDROOMS: dict[str, int] = {
    "1-ROOM": 1, "2-ROOM": 1, "3-ROOM": 2,
    "4-ROOM": 3, "5-ROOM": 3, "EXECUTIVE": 4,
}

SG_FLAT_AREA: dict[str, tuple[int, int]] = {
    "1-ROOM": (23, 31), "2-ROOM": (36, 45),
    "3-ROOM": (60, 70), "4-ROOM": (80, 95),
    "5-ROOM": (100, 115), "EXECUTIVE": (115, 140),
}

SG_DISTRICT_CN: dict[str, str] = {
    "CLEMENTI": "新加坡-金文泰", "QUEENSTOWN": "新加坡-女皇镇",
    "BUKIT TIMAH": "新加坡-武吉知马", "BUKIT MERAH": "新加坡-红山",
    "JURONG EAST": "新加坡-裕廊东", "JURONG WEST": "新加坡-裕廊西",
}

SG_TOWN_CN: dict[str, str] = {
    "CLEMENTI": "金文泰", "QUEENSTOWN": "女皇镇",
    "BUKIT TIMAH": "武吉知马", "BUKIT MERAH": "红山",
    "JURONG EAST": "裕廊东", "JURONG WEST": "裕廊西",
}

SG_FLAT_CN: dict[str, str] = {
    "1-ROOM": "一房式", "2-ROOM": "两房式", "3-ROOM": "三房式",
    "4-ROOM": "四房式", "5-ROOM": "五房式", "EXECUTIVE": "公寓式",
}


# ═══════════════════════════════════════════════
# 伦敦 — 常量 & 映射 (Inside Airbnb)
# ═══════════════════════════════════════════════

UK_ROOM_TYPE_MAP: dict[str, PropertyType] = {
    "Entire home/apt": PropertyType.apartment,
    "Private room": PropertyType.shared,
    "Shared room": PropertyType.shared,
}

UK_NEIGHBOURHOOD_CN: dict[str, str] = {
    "Westminster": "威斯敏斯特", "Kensington and Chelsea": "肯辛顿/切尔西",
    "Hammersmith and Fulham": "哈默史密斯", "Wandsworth": "旺兹沃思",
    "Lambeth": "兰贝斯", "Southwark": "南华克",
    "Tower Hamlets": "塔村区", "Hackney": "哈克尼",
    "Islington": "伊斯灵顿", "Camden": "卡姆登",
    "Brent": "布伦特", "Ealing": "伊灵", "Hounslow": "豪恩斯洛",
    "Richmond upon Thames": "里士满", "Kingston upon Thames": "金斯顿",
    "Merton": "默顿", "Sutton": "萨顿", "Croydon": "克罗伊登",
    "Bromley": "布罗姆利", "Lewisham": "刘易舍姆",
    "Greenwich": "格林威治", "Newham": "纽汉",
    "Haringey": "哈林盖", "Enfield": "恩菲尔德",
    "Barnet": "巴尼特", "Harrow": "哈罗", "Hillingdon": "希灵登",
    "Redbridge": "雷德布里奇", "Waltham Forest": "沃尔瑟姆森林",
    "Barking and Dagenham": "巴金", "Havering": "黑弗灵",
    "Bexley": "贝克斯利",
}

UK_UNI_NEAR: dict[str, str] = {
    "Westminster": "UCL/LSE/Imperial/King's",
    "Kensington and Chelsea": "Imperial College London",
    "Camden": "UCL/London Business School",
    "Islington": "City, University of London",
    "Tower Hamlets": "Queen Mary University",
    "Southwark": "King's College/LSE",
    "Lambeth": "King's College/LSE",
    "Hammersmith and Fulham": "Imperial College",
    "Hackney": "UCL/City University",
    "Greenwich": "University of Greenwich",
    "Kingston upon Thames": "Kingston University",
    "Hillingdon": "Brunel University",
}


# ═══════════════════════════════════════════════
# 新加坡数据处理
# ═══════════════════════════════════════════════

def load_sg_properties(limit: int = 500) -> list[dict]:
    """从CSV加载新加坡HDB租金数据，过滤NUS周边区域并采样"""
    if not SG_CSV.exists():
        print(f"[WARN] 新加坡CSV不存在: {SG_CSV}")
        return []

    rows = []
    with open(SG_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            town = row.get("town", "").upper()
            if town not in SG_NUS_TOWNS:
                continue
            year = safe_int(row.get("year", 0))
            if year < 2024:
                continue
            rows.append(row)

    print(f"[SG] NUS周边2024-2026年数据: {len(rows)} 条")

    if len(rows) > limit:
        random.seed(42)
        rows = random.sample(rows, limit)
        print(f"[SG] 采样至 {limit} 条")

    properties = []
    for row in rows:
        flat_type = row.get("flat_type", "4-ROOM")
        bedrooms = SG_FLAT_BEDROOMS.get(flat_type, 2)
        bathrooms = max(1, bedrooms - 1) if bedrooms > 1 else 1

        area_min, area_max = SG_FLAT_AREA.get(flat_type, (60, 80))
        area_sqm = Decimal(str(random.randint(area_min, area_max)))

        town = row.get("town", "")
        town_cn = SG_TOWN_CN.get(town, town)
        district = SG_DISTRICT_CN.get(town, f"新加坡-{town_cn}")

        monthly_rent = safe_int(row.get("monthly_rent", 0))
        if monthly_rent <= 0:
            continue
        price_cny = int(monthly_rent * 5.3)

        lat = safe_float(row.get("lat", 0))
        lon = safe_float(row.get("lon", 0))
        if lat and lon:
            lat, lon = jitter_coord(lat, lon, 200)

        flat_cn = SG_FLAT_CN.get(flat_type, flat_type)
        title = f"NUS周边·{town_cn}{flat_cn}HDB·月租SGD{monthly_rent}"
        if len(title) > 200:
            title = title[:197] + "..."

        block = row.get("block", "")
        street = row.get("street_name", "")
        address = f"Blk {block} {street}, Singapore"[:300]

        amenities = random.choice([
            ["空调", "WiFi", "家具齐全", "近地铁"],
            ["空调", "WiFi", "家具齐全", "近地铁", "高层通风"],
            ["空调", "WiFi", "家具齐全", "近超市", "安静社区"],
            ["空调", "WiFi", "全屋家电", "近地铁", "近超市", "高层通风"],
            ["空调", "WiFi", "新装修", "家具齐全", "近校园"],
        ])

        description = (
            f"{town_cn}{flat_cn}HDB组屋。月租SGD{monthly_rent}（约CNY{price_cny}）。"
            f"{bedrooms}卧{bathrooms}卫，面积约{area_sqm}平米。"
            f"坐标({lat}, {lon})，靠近NUS，通勤便利。"
            f"HDB官方备案数据，{row.get('rent_approval_date', '')} 批准。"
        )[:2000]

        properties.append({
            "title": title,
            "description": description,
            "address": address,
            "district": district,
            "country": "SG",
            "price_monthly": Decimal(price_cny),
            "area_sqm": area_sqm,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "property_type": PropertyType.apartment,
            "latitude": Decimal(str(lat)) if lat else None,
            "longitude": Decimal(str(lon)) if lon else None,
            "deposit_amount": monthly_rent,
            "deposit_type": DepositType.one_month,
            "amenities": amenities,
            "available_from": random_date_in_range(14, 150),
            "min_stay_months": random.choice([3, 6, 12]),
            "min_lease_months": random.choice([3, 6, 12]),
            "max_lease_months": random.choice([12, 24, 36, 60]),
            "floor": random.randint(2, 40),
            "room_number": f"{random.randint(2,40):02d}-{random.randint(1,99):02d}",
            "institute_id": 2,
        })

    return properties


# ═══════════════════════════════════════════════
# 伦敦数据处理 (Inside Airbnb)
# ═══════════════════════════════════════════════

def load_uk_properties(limit: int = 500) -> list[dict]:
    """从CSV加载伦敦Airbnb数据，筛选长租可用房源并采样"""
    if not UK_CSV.exists():
        print(f"[WARN] 英国CSV不存在: {UK_CSV}")
        return []

    rows = []
    with open(UK_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            price_str = safe_str(row.get("price", "0")).replace("$", "").replace(",", "")
            nightly = safe_float(price_str)
            if nightly < 20 or nightly > 500:
                continue
            min_nights = safe_int(row.get("minimum_nights", 999))
            if min_nights > 90:
                continue
            avail = safe_int(row.get("availability_365", 0))
            if avail <= 0:
                continue
            rows.append(row)

    print(f"[UK] Airbnb筛选(日租$20-500, min_nights<=90, available>0): {len(rows)} 条")

    if len(rows) > limit:
        random.seed(42)
        rows = random.sample(rows, limit)
        print(f"[UK] 采样至 {limit} 条")

    properties = []
    for row in rows:
        name = safe_str(row.get("name", "London Apartment"))
        neighbourhood = safe_str(row.get("neighbourhood", ""))
        room_type = safe_str(row.get("room_type", "Entire home/apt"))

        property_type = UK_ROOM_TYPE_MAP.get(room_type, PropertyType.apartment)

        nightly = safe_float(safe_str(row.get("price", "0")).replace("$", "").replace(",", ""))
        min_nights = safe_int(row.get("minimum_nights", 1), 1)
        monthly_est = int(nightly * 25)
        price_cny = int(monthly_est * 9.1)

        lat = safe_float(row.get("latitude", 0))
        lon = safe_float(row.get("longitude", 0))
        if lat and lon:
            lat, lon = jitter_coord(lat, lon, 100)

        reviews = safe_int(row.get("number_of_reviews", 0))
        availability = safe_int(row.get("availability_365", 0))

        area_cn = UK_NEIGHBOURHOOD_CN.get(neighbourhood, neighbourhood)
        if not area_cn:
            area_cn = neighbourhood or "伦敦"
        district = f"伦敦-{area_cn}"

        uni = UK_UNI_NEAR.get(neighbourhood, "University of London")

        type_cn_map = {
            PropertyType.apartment: "整套公寓",
            PropertyType.shared: "独立房间",
            PropertyType.house: "整套House",
            PropertyType.studio: "Studio",
        }
        type_cn = type_cn_map.get(property_type, "公寓")

        if room_type == "Entire home/apt":
            area_sqm = Decimal(str(random.randint(30, 80)))
        elif room_type == "Private room":
            area_sqm = Decimal(str(random.randint(12, 25)))
        else:
            area_sqm = Decimal(str(random.randint(10, 20)))

        title = f"伦敦{area_cn}·{type_cn}·月租约GBP{monthly_est}"
        if len(title) > 200:
            title = title[:197] + "..."

        amenities = random.choice([
            ["WiFi", "暖气", "厨房", "洗衣机"],
            ["WiFi", "暖气", "厨房", "洗衣机", "阳台"],
            ["WiFi", "暖气", "厨房", "洗衣机/烘干机"],
            ["WiFi", "暖气", "厨房", "24小时入住", "近地铁"],
            ["WiFi", "暖气", "厨房", "洗衣机", "免费停车"],
        ])

        description = (
            f"Airbnb真实房源:「{name}」。日租GBP{nightly}，"
            f"估算长租月租GBP{monthly_est}（CNY{price_cny}）。"
            f"位于伦敦{area_cn}，靠近{uni}。{type_cn}，约{int(area_sqm)}平米。"
            f"最短{min_nights}晚起租，{availability}天内可订。{reviews}条住客评价。"
        )[:2000]

        properties.append({
            "title": title,
            "description": description,
            "address": name[:300],
            "district": district,
            "country": "GB",
            "price_monthly": Decimal(price_cny),
            "area_sqm": area_sqm,
            "bedrooms": 1 if room_type != "Entire home/apt" else random.choice([1, 1, 2]),
            "bathrooms": 1,
            "property_type": property_type,
            "latitude": Decimal(str(lat)) if lat else None,
            "longitude": Decimal(str(lon)) if lon else None,
            "deposit_amount": monthly_est,
            "deposit_type": DepositType.one_month,
            "amenities": amenities,
            "available_from": random_date_in_range(14, 150),
            "min_stay_months": max(1, min_nights // 30),
            "min_lease_months": random.choice([1, 3, 6]),
            "max_lease_months": random.choice([6, 12, 24]),
            "floor": random.randint(0, 10),
            "room_number": "",
            "institute_id": None,
        })

    return properties


# ═══════════════════════════════════════════════
# 种子写入
# ═══════════════════════════════════════════════

async def seed_real_properties(
    dry_run: bool = False,
    clear_existing: bool = False,
    sg_only: bool = False,
    uk_only: bool = False,
):
    """导入新加坡和伦敦真实租房数据"""

    sg_props = []
    uk_props = []

    if not uk_only:
        sg_props = load_sg_properties(limit=500)
        print(f"[SG] 准备导入 {len(sg_props)} 套HDB房源")
    if not sg_only:
        uk_props = load_uk_properties(limit=500)
        print(f"[UK] 准备导入 {len(uk_props)} 套Airbnb房源")

    all_props = sg_props + uk_props
    if not all_props:
        print("[ERROR] 没有数据可导入！")
        return

    print(f"[总计] {len(all_props)} 套房源待处理\n")

    if dry_run:
        print("=== DRY RUN MODE ===\n")
        for i, p in enumerate(all_props):
            flag = {"SG": "[SG]", "GB": "[UK]"}.get(p["country"], "[??]")
            print(f"  [{i+1:03d}] {flag} {p['title'][:70]}")
            print(f"         {p['district']} | CNY{p['price_monthly']}/月 | "
                  f"{p['bedrooms']}室{p['bathrooms']}卫 | {p['property_type'].value}")
            lat, lon = p.get("latitude"), p.get("longitude")
            if lat and lon:
                print(f"         ({lat}, {lon})")
        sg_c = sum(1 for p in all_props if p["country"] == "SG")
        uk_c = sum(1 for p in all_props if p["country"] == "GB")
        print(f"\n[DRY RUN] SG {sg_c} + UK {uk_c} = {len(all_props)} 套房源")
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.role == "landlord").limit(10)
        )
        landlords = result.scalars().all()

        if not landlords:
            print("[ERROR] 没有找到房东账号！")
            return

        landlord_ids = [l.id for l in landlords]
        print(f"房东: {[(l.id, l.username) for l in landlords]}\n")

        if clear_existing:
            for country, label in [("SG", "新加坡"), ("GB", "伦敦")]:
                if (country == "SG" and uk_only) or (country == "GB" and sg_only):
                    continue
                del_r = await session.execute(
                    delete(Property).where(Property.country == country)
                )
                print(f"[CLEAR] 已删除 {del_r.rowcount} 套{label}房源")
            await session.flush()
            print()

        created = 0
        sg_created = 0
        uk_created = 0

        for i, pdata in enumerate(all_props):
            landlord_id = landlord_ids[i % len(landlord_ids)]

            prop = Property(
                landlord_id=landlord_id,
                status=PropertyStatus.available,
                rent_type=RentType.monthly,
                title=pdata["title"],
                description=pdata.get("description"),
                address=pdata["address"],
                district=pdata["district"],
                country=pdata["country"],
                price_monthly=pdata["price_monthly"],
                area_sqm=pdata.get("area_sqm"),
                bedrooms=pdata["bedrooms"],
                bathrooms=pdata["bathrooms"],
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
                room_number=pdata.get("room_number"),
                institute_id=pdata.get("institute_id"),
                service_fee_rate=0.10,
            )
            session.add(prop)
            created += 1
            if pdata["country"] == "SG":
                sg_created += 1
            else:
                uk_created += 1

            if created % 100 == 0:
                print(f"  [{created:04d}] ...")

        await session.commit()
        print(f"\n{'='*60}")
        print(f"[DONE] SG {sg_created} + UK {uk_created} = {created} 套真实房源导入完成！")
        print(f"{'='*60}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    clear = "--clear-existing" in sys.argv
    sg_only = "--sg-only" in sys.argv
    uk_only = "--uk-only" in sys.argv
    asyncio.run(seed_real_properties(
        dry_run=dry, clear_existing=clear, sg_only=sg_only, uk_only=uk_only,
    ))

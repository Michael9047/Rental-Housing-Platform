from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, delete, text
from app.db.session import async_session_maker
from app.models.institute import Institute, InstituteStatus
from app.models.unit_type import UnitType, UnitTypeStatus, PropertyType, DepositType
from app.models.poi import InstitutePOI
from app.models.institute_commute import InstituteCommute
from app.models.university import University
from app.models.user import User, UserRole, UserStatus
from app.core.config import get_settings

# ═══════════════════════════════════════════════════════════════════
# 新加坡定价常量（SGD/月）
# ═══════════════════════════════════════════════════════════════════

ROOM_TYPE_BASE: dict[str, Decimal] = {
    "shared":  Decimal("650"), "common":  Decimal("850"),
    "ensuite": Decimal("1000"), "master":  Decimal("1250"),
    "studio":  Decimal("1700"), "1bed":    Decimal("2000"),
    "2bed":    Decimal("3000"), "3bed":    Decimal("3800"),
}

ZONE_ADJ: dict[str, Decimal] = {
    "suburb": Decimal("-0.08"), "west": Decimal("-0.03"),
    "central_west": Decimal("+0.05"), "city_fringe": Decimal("+0.08"),
    "city": Decimal("+0.12"),
}

MRT_ADJ: dict[str, Decimal] = {
    "near": Decimal("+0.06"), "mid": Decimal("+0.01"), "far": Decimal("-0.05"),
}

UNI_ADJ: dict[str, Decimal] = {
    "near": Decimal("+0.06"), "mid": Decimal("+0.01"), "far": Decimal("-0.03"),
}

ROOM_AMENITY_ADDERS: dict[str, Decimal] = {
    "空调": Decimal("30"), "独立卫浴": Decimal("120"), "阳台": Decimal("100"),
    "书桌": Decimal("20"), "洗衣机": Decimal("30"), "冰箱": Decimal("20"),
    "WiFi免费": Decimal("15"), "电视": Decimal("20"), "微波炉": Decimal("15"),
    "衣柜": Decimal("15"), "独立厨房": Decimal("80"), "可做饭": Decimal("40"),
    "包水电": Decimal("100"), "禁烟房": Decimal("10"), "宠物友好": Decimal("50"),
    "智能门锁": Decimal("15"),
}

BUILDING_AMENITY_SHOW: set[str] = {
    "健身房", "泳池", "自习室", "洗衣房", "24小时安保",
    "电梯", "停车位", "网球场", "BBQ区", "校车接驳", "快递代收", "门禁系统",
}
BASELINE_AMENITIES = {"家具齐全", "精装修"}

# ═══════════════════════════════════════════════════════════════════
# 伦敦定价常量（GBP/周）
# ═══════════════════════════════════════════════════════════════════

ROOM_TYPE_BASE_GB: dict[str, Decimal] = {
    "shared": Decimal("175"), "common": Decimal("210"),
    "ensuite": Decimal("290"), "master": Decimal("260"),
    "studio": Decimal("380"), "1bed": Decimal("450"), "2bed": Decimal("600"),
}

ZONE_ADJ_GB: dict[str, Decimal] = {
    "zone3": Decimal("-0.08"), "zone2": Decimal("+0.02"), "zone1": Decimal("+0.14"),
}

TUBE_ADJ: dict[str, Decimal] = {
    "near": Decimal("+0.07"), "mid": Decimal("+0.02"), "far": Decimal("-0.04"),
}

UNI_ADJ_GB: dict[str, Decimal] = {
    "near": Decimal("+0.08"), "mid": Decimal("+0.02"), "far": Decimal("-0.04"),
}

ROOM_AMENITY_ADDERS_GB: dict[str, Decimal] = {
    "独立卫浴": Decimal("65"), "暖气": Decimal("25"), "阳台": Decimal("40"),
    "书桌": Decimal("10"), "双人床": Decimal("20"), "洗衣机": Decimal("20"),
    "冰箱": Decimal("10"), "WiFi免费": Decimal("15"), "包Bill": Decimal("30"),
    "禁烟房": Decimal("5"), "宠物友好": Decimal("25"), "智能门锁": Decimal("5"),
    "微波炉": Decimal("8"), "衣柜": Decimal("10"), "地毯": Decimal("5"),
    "双层玻璃": Decimal("10"), "空调": Decimal("0"),
}

# ═══════════════════════════════════════════════════════════════════
# 价格计算
# ═══════════════════════════════════════════════════════════════════

def compute_price(
    room_type: str, zone: str, mrt_proximity: str,
    uni_proximity: str, room_amenities: list[str], country: str = "SG",
) -> tuple[Decimal, dict[str, Decimal]]:
    breakdown: dict[str, Decimal] = {}
    is_gb = country == "GB"

    base_table = ROOM_TYPE_BASE_GB if is_gb else ROOM_TYPE_BASE
    zone_table = ZONE_ADJ_GB if is_gb else ZONE_ADJ
    transit_table = TUBE_ADJ if is_gb else MRT_ADJ
    uni_table = UNI_ADJ_GB if is_gb else UNI_ADJ
    adder_table = ROOM_AMENITY_ADDERS_GB if is_gb else ROOM_AMENITY_ADDERS
    rounding = Decimal("5")

    base = base_table.get(room_type, Decimal("250") if is_gb else Decimal("1000"))
    breakdown["基准价"] = base
    zone_adj = zone_table.get(zone, Decimal("0"))
    transit_adj = transit_table.get(mrt_proximity, Decimal("0"))
    uni_adj = uni_table.get(uni_proximity, Decimal("0"))
    location_mult = Decimal("1.0") + zone_adj + transit_adj + uni_adj
    breakdown["区位调整"] = zone_adj + transit_adj + uni_adj
    price = base * location_mult
    breakdown["区位后价格"] = price
    adder_total = Decimal("0")
    for a in room_amenities:
        if a in adder_table:
            adder_total += adder_table[a]
    price += adder_total
    breakdown["配套加价"] = adder_total
    jitter = Decimal(str(round(random.uniform(0.95, 1.05), 4)))
    price *= jitter
    breakdown["抖动"] = jitter
    price = Decimal(int(price / rounding)) * rounding
    return price, breakdown


# ═══════════════════════════════════════════════════════════════════
# POI 模板
# ═══════════════════════════════════════════════════════════════════

POI_TEMPLATES: dict[str, list[dict]] = {
    "clementi": [
        {"category": "subway_station", "name": "Clementi MRT", "lat": 1.3150, "lng": 103.7645, "distance_m": 250},
        {"category": "mall", "name": "Clementi Mall", "lat": 1.3153, "lng": 103.7650, "distance_m": 300},
        {"category": "supermarket", "name": "FairPrice Clementi", "lat": 1.3150, "lng": 103.7652, "distance_m": 320},
        {"category": "hawker_centre", "name": "Clementi 448 Market", "lat": 1.3140, "lng": 103.7630, "distance_m": 200},
        {"category": "hospital", "name": "National University Hospital", "lat": 1.2940, "lng": 103.7830, "distance_m": 2800},
        {"category": "gym", "name": "Anytime Fitness Clementi", "lat": 1.3152, "lng": 103.7645, "distance_m": 300},
    ],
    "dover": [
        {"category": "subway_station", "name": "Dover MRT", "lat": 1.3040, "lng": 103.7790, "distance_m": 550},
        {"category": "supermarket", "name": "FairPrice Dover", "lat": 1.3045, "lng": 103.7780, "distance_m": 520},
        {"category": "hawker_centre", "name": "Dover Road Food Centre", "lat": 1.3040, "lng": 103.7775, "distance_m": 600},
    ],
    "west_coast": [
        {"category": "bus_station", "name": "West Coast Rd Bus Stop", "lat": 1.3100, "lng": 103.7550, "distance_m": 120},
        {"category": "subway_station", "name": "Clementi MRT", "lat": 1.3150, "lng": 103.7645, "distance_m": 1100},
        {"category": "supermarket", "name": "Giant West Coast", "lat": 1.3105, "lng": 103.7540, "distance_m": 150},
        {"category": "hawker_centre", "name": "West Coast Market Square", "lat": 1.3105, "lng": 103.7560, "distance_m": 100},
    ],
    "buona_vista": [
        {"category": "subway_station", "name": "Buona Vista MRT", "lat": 1.3070, "lng": 103.7900, "distance_m": 200},
        {"category": "mall", "name": "The Star Vista", "lat": 1.3065, "lng": 103.7890, "distance_m": 180},
        {"category": "supermarket", "name": "Cold Storage The Star Vista", "lat": 1.3065, "lng": 103.7890, "distance_m": 180},
        {"category": "gym", "name": "Fitness First Buona Vista", "lat": 1.3065, "lng": 103.7900, "distance_m": 200},
    ],
    "jurong_west": [
        {"category": "subway_station", "name": "Jurong East MRT", "lat": 1.3330, "lng": 103.7430, "distance_m": 600},
        {"category": "mall", "name": "Jem / Westgate", "lat": 1.3330, "lng": 103.7420, "distance_m": 650},
        {"category": "supermarket", "name": "FairPrice Jurong West", "lat": 1.3405, "lng": 103.7095, "distance_m": 400},
        {"category": "hawker_centre", "name": "Jurong West 505 Market", "lat": 1.3405, "lng": 103.7110, "distance_m": 200},
        {"category": "hospital", "name": "Ng Teng Fong General Hospital", "lat": 1.3340, "lng": 103.7435, "distance_m": 800},
    ],
    "pioneer": [
        {"category": "subway_station", "name": "Pioneer MRT", "lat": 1.3370, "lng": 103.6970, "distance_m": 200},
        {"category": "supermarket", "name": "Giant Pioneer", "lat": 1.3380, "lng": 103.6975, "distance_m": 250},
        {"category": "hawker_centre", "name": "Pioneer Mall Food Court", "lat": 1.3385, "lng": 103.6975, "distance_m": 300},
    ],
    "boon_lay": [
        {"category": "subway_station", "name": "Boon Lay MRT", "lat": 1.3350, "lng": 103.7050, "distance_m": 250},
        {"category": "mall", "name": "Jurong Point", "lat": 1.3360, "lng": 103.7060, "distance_m": 350},
        {"category": "supermarket", "name": "FairPrice Xtra Jurong Point", "lat": 1.3360, "lng": 103.7060, "distance_m": 350},
        {"category": "gym", "name": "Anytime Fitness Jurong Point", "lat": 1.3360, "lng": 103.7060, "distance_m": 350},
    ],
    "lakeside": [
        {"category": "subway_station", "name": "Lakeside MRT", "lat": 1.3450, "lng": 103.7200, "distance_m": 500},
        {"category": "supermarket", "name": "FairPrice Lakeside", "lat": 1.3455, "lng": 103.7210, "distance_m": 550},
        {"category": "hawker_centre", "name": "Taman Jurong Market", "lat": 1.3400, "lng": 103.7230, "distance_m": 700},
    ],
    "bugis": [
        {"category": "subway_station", "name": "Bugis MRT", "lat": 1.3000, "lng": 103.8550, "distance_m": 200},
        {"category": "mall", "name": "Bugis Junction", "lat": 1.2995, "lng": 103.8555, "distance_m": 150},
        {"category": "supermarket", "name": "Cold Storage Bugis Junction", "lat": 1.2995, "lng": 103.8555, "distance_m": 150},
        {"category": "hawker_centre", "name": "Albert Centre Market", "lat": 1.3020, "lng": 103.8540, "distance_m": 300},
        {"category": "hospital", "name": "Raffles Hospital", "lat": 1.3015, "lng": 103.8555, "distance_m": 300},
        {"category": "gym", "name": "Fitness First Bugis", "lat": 1.3005, "lng": 103.8545, "distance_m": 220},
    ],
    "kallang": [
        {"category": "subway_station", "name": "Kallang MRT", "lat": 1.3100, "lng": 103.8700, "distance_m": 550},
        {"category": "supermarket", "name": "FairPrice Kallang", "lat": 1.3105, "lng": 103.8710, "distance_m": 600},
        {"category": "hawker_centre", "name": "Old Airport Road Food Centre", "lat": 1.3080, "lng": 103.8860, "distance_m": 1800},
    ],
    "lavender": [
        {"category": "subway_station", "name": "Lavender MRT", "lat": 1.3050, "lng": 103.8600, "distance_m": 250},
        {"category": "supermarket", "name": "FairPrice Lavender", "lat": 1.3055, "lng": 103.8595, "distance_m": 280},
        {"category": "mall", "name": "City Square Mall", "lat": 1.3110, "lng": 103.8570, "distance_m": 800},
    ],
    "woodlands": [
        {"category": "subway_station", "name": "Woodlands MRT", "lat": 1.4380, "lng": 103.7890, "distance_m": 1100},
        {"category": "mall", "name": "Causeway Point", "lat": 1.4380, "lng": 103.7880, "distance_m": 1050},
        {"category": "supermarket", "name": "FairPrice Woodlands", "lat": 1.4375, "lng": 103.7885, "distance_m": 1000},
    ],
    # ── London POIs ──
    "bloomsbury": [
        {"category": "subway_station", "name": "Russell Square", "lat": 51.5230, "lng": -0.1243, "distance_m": 200},
        {"category": "supermarket", "name": "Tesco Express Brunswick", "lat": 51.5240, "lng": -0.1240, "distance_m": 180},
        {"category": "restaurant", "name": "Bloomsbury Street restaurants", "lat": 51.5220, "lng": -0.1260, "distance_m": 250},
        {"category": "mall", "name": "The Brunswick Centre", "lat": 51.5240, "lng": -0.1230, "distance_m": 300},
        {"category": "hospital", "name": "UCL Hospital", "lat": 51.5250, "lng": -0.1340, "distance_m": 800},
        {"category": "gym", "name": "The Gym Bloomsbury", "lat": 51.5230, "lng": -0.1220, "distance_m": 300},
    ],
    "kings_cross": [
        {"category": "subway_station", "name": "King's Cross St Pancras", "lat": 51.5300, "lng": -0.1230, "distance_m": 400},
        {"category": "supermarket", "name": "Waitrose Granary Square", "lat": 51.5320, "lng": -0.1240, "distance_m": 300},
        {"category": "restaurant", "name": "Dishoom King's Cross", "lat": 51.5310, "lng": -0.1235, "distance_m": 350},
        {"category": "gym", "name": "Frame King's Cross", "lat": 51.5310, "lng": -0.1250, "distance_m": 350},
    ],
    "south_kensington": [
        {"category": "subway_station", "name": "South Kensington", "lat": 51.4940, "lng": -0.1738, "distance_m": 300},
        {"category": "supermarket", "name": "Sainsbury's Cromwell Rd", "lat": 51.4950, "lng": -0.1770, "distance_m": 350},
        {"category": "mall", "name": "Harrods", "lat": 51.4990, "lng": -0.1630, "distance_m": 1200},
        {"category": "hospital", "name": "Royal Marsden Hospital", "lat": 51.4910, "lng": -0.1720, "distance_m": 500},
        {"category": "gym", "name": "Imperial College Ethos", "lat": 51.4980, "lng": -0.1760, "distance_m": 250},
    ],
    "hammersmith": [
        {"category": "subway_station", "name": "Hammersmith", "lat": 51.4930, "lng": -0.2250, "distance_m": 300},
        {"category": "supermarket", "name": "Tesco Hammersmith", "lat": 51.4920, "lng": -0.2260, "distance_m": 350},
        {"category": "mall", "name": "Westfield London", "lat": 51.5070, "lng": -0.2210, "distance_m": 1700},
    ],
    "holborn": [
        {"category": "subway_station", "name": "Holborn", "lat": 51.5170, "lng": -0.1200, "distance_m": 200},
        {"category": "supermarket", "name": "Sainsbury's Holborn", "lat": 51.5180, "lng": -0.1190, "distance_m": 220},
        {"category": "restaurant", "name": "Holborn Dining Room", "lat": 51.5175, "lng": -0.1180, "distance_m": 300},
        {"category": "hospital", "name": "Great Ormond St Hospital", "lat": 51.5220, "lng": -0.1200, "distance_m": 600},
        {"category": "gym", "name": "Gymbox Holborn", "lat": 51.5180, "lng": -0.1210, "distance_m": 200},
    ],
    "waterloo": [
        {"category": "subway_station", "name": "Waterloo", "lat": 51.5030, "lng": -0.1130, "distance_m": 250},
        {"category": "supermarket", "name": "Tesco Waterloo", "lat": 51.5035, "lng": -0.1120, "distance_m": 280},
        {"category": "restaurant", "name": "South Bank restaurants", "lat": 51.5050, "lng": -0.1150, "distance_m": 350},
        {"category": "hospital", "name": "St Thomas' Hospital", "lat": 51.4990, "lng": -0.1180, "distance_m": 600},
    ],
    "earls_court": [
        {"category": "subway_station", "name": "Earl's Court", "lat": 51.4910, "lng": -0.1940, "distance_m": 250},
        {"category": "supermarket", "name": "Tesco Earl's Court", "lat": 51.4920, "lng": -0.1930, "distance_m": 300},
        {"category": "restaurant", "name": "Earl's Court Rd restaurants", "lat": 51.4915, "lng": -0.1920, "distance_m": 200},
    ],
    "camden": [
        {"category": "subway_station", "name": "Camden Town", "lat": 51.5390, "lng": -0.1420, "distance_m": 400},
        {"category": "supermarket", "name": "Sainsbury's Camden", "lat": 51.5380, "lng": -0.1430, "distance_m": 450},
        {"category": "mall", "name": "Camden Market", "lat": 51.5415, "lng": -0.1465, "distance_m": 550},
    ],
    "fitzrovia": [
        {"category": "subway_station", "name": "Goodge Street", "lat": 51.5200, "lng": -0.1340, "distance_m": 200},
        {"category": "supermarket", "name": "Tesco Goodge Street", "lat": 51.5195, "lng": -0.1350, "distance_m": 250},
        {"category": "restaurant", "name": "Charlotte Street restaurants", "lat": 51.5190, "lng": -0.1360, "distance_m": 300},
        {"category": "hospital", "name": "UCL Hospital", "lat": 51.5250, "lng": -0.1340, "distance_m": 600},
    ],
    "gloucester_road": [
        {"category": "subway_station", "name": "Gloucester Road", "lat": 51.4945, "lng": -0.1830, "distance_m": 200},
        {"category": "supermarket", "name": "Waitrose Gloucester Rd", "lat": 51.4950, "lng": -0.1820, "distance_m": 250},
        {"category": "restaurant", "name": "Gloucester Rd eateries", "lat": 51.4950, "lng": -0.1830, "distance_m": 200},
        {"category": "hospital", "name": "The Cromwell Hospital", "lat": 51.4955, "lng": -0.1860, "distance_m": 400},
    ],
    "shepherds_bush": [
        {"category": "subway_station", "name": "Shepherd's Bush", "lat": 51.5050, "lng": -0.2210, "distance_m": 400},
        {"category": "supermarket", "name": "Lidl Shepherd's Bush", "lat": 51.5055, "lng": -0.2220, "distance_m": 350},
        {"category": "mall", "name": "Westfield London", "lat": 51.5070, "lng": -0.2210, "distance_m": 500},
    ],
    "london_bridge": [
        {"category": "subway_station", "name": "London Bridge", "lat": 51.5050, "lng": -0.0860, "distance_m": 300},
        {"category": "supermarket", "name": "M&S London Bridge", "lat": 51.5055, "lng": -0.0850, "distance_m": 280},
        {"category": "restaurant", "name": "Borough Market", "lat": 51.5055, "lng": -0.0900, "distance_m": 500},
        {"category": "hospital", "name": "Guy's Hospital", "lat": 51.5030, "lng": -0.0870, "distance_m": 250},
    ],
    "bermondsey": [
        {"category": "subway_station", "name": "Bermondsey", "lat": 51.4970, "lng": -0.0640, "distance_m": 500},
        {"category": "supermarket", "name": "Tesco Bermondsey", "lat": 51.4965, "lng": -0.0630, "distance_m": 550},
        {"category": "restaurant", "name": "Bermondsey St eateries", "lat": 51.4980, "lng": -0.0700, "distance_m": 700},
    ],
    "pimlico": [
        {"category": "subway_station", "name": "Pimlico", "lat": 51.4890, "lng": -0.1330, "distance_m": 300},
        {"category": "supermarket", "name": "Tesco Pimlico", "lat": 51.4895, "lng": -0.1340, "distance_m": 280},
        {"category": "restaurant", "name": "Warwick Way eateries", "lat": 51.4890, "lng": -0.1350, "distance_m": 250},
    ],
    "shoreditch": [
        {"category": "subway_station", "name": "Old Street", "lat": 51.5260, "lng": -0.0880, "distance_m": 500},
        {"category": "supermarket", "name": "Tesco Old Street", "lat": 51.5265, "lng": -0.0870, "distance_m": 480},
        {"category": "restaurant", "name": "Shoreditch High St", "lat": 51.5240, "lng": -0.0780, "distance_m": 600},
    ],
    "angel": [
        {"category": "subway_station", "name": "Angel", "lat": 51.5320, "lng": -0.1060, "distance_m": 250},
        {"category": "supermarket", "name": "Sainsbury's Angel", "lat": 51.5325, "lng": -0.1050, "distance_m": 280},
        {"category": "restaurant", "name": "Upper Street restaurants", "lat": 51.5340, "lng": -0.1040, "distance_m": 400},
    ],
    "chelsea": [
        {"category": "subway_station", "name": "Sloane Square", "lat": 51.4920, "lng": -0.1570, "distance_m": 500},
        {"category": "supermarket", "name": "Waitrose King's Road", "lat": 51.4890, "lng": -0.1640, "distance_m": 600},
        {"category": "restaurant", "name": "King's Road eateries", "lat": 51.4900, "lng": -0.1620, "distance_m": 550},
        {"category": "hospital", "name": "Chelsea & Westminster", "lat": 51.4840, "lng": -0.1820, "distance_m": 2000},
    ],
}

# ═══════════════════════════════════════════════════════════════════
# Institute 配置（12 栋 SG + 20 栋 London）
# ═══════════════════════════════════════════════════════════════════

INSTITUTE_CONFIGS: list[dict[str, Any]] = [
    # ═══ SG: Condo 整租型 — 做 studio / 1bed / 2bed ═══
    {
        "name": "Clementi Peak Residences", "name_cn": "金文泰峰尚公寓", "abbreviation": "CPR",
        "category": "Condo", "zone": "central_west",
        "lat": 1.3160, "lng": 103.7655,
        "address": "12 Clementi Ave 1, Singapore 129957",
        "street": "Clementi Ave 1", "district": "Clementi", "city": "Singapore", "country": "SG",
        "npc": "CL-NPC", "postal_code": "129957",
        "building_type": "condominium", "total_floors": 25, "total_units": 200, "year_built": 2018, "has_elevator": True,
        "description": "金文泰核心地段高端公寓，步行 3 分钟到 Clementi MRT 和 Clementi Mall。NUS 学生首选。",
        "building_amenities": ["健身房", "泳池", "自习室", "24小时安保", "电梯", "停车位", "BBQ区", "门禁系统", "快递代收"],
        "poi_zone": "clementi", "mrt_proximity": "near", "target_uni": "NUS", "uni_id": 1, "uni_proximity": "near",
        "commute": {"transit_min": 12, "walk_min": 25, "drive_min": 5},
        "unit_types": [
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("22"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "智能门锁"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("30"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "阳台", "洗衣机", "冰箱", "智能门锁"]},
            {"type": "1bed", "tier": "standard", "area_sqm": Decimal("38"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "智能门锁"]},
            {"type": "1bed", "tier": "premium", "area_sqm": Decimal("48"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "阳台", "洗衣机", "冰箱", "电视", "智能门锁"]},
            {"type": "2bed", "tier": "standard", "area_sqm": Decimal("62"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "阳台", "洗衣机", "冰箱", "电视"]},
        ],
    },
    {
        "name": "Buona Vista Suites", "name_cn": "波那维斯达公馆", "abbreviation": "BVS",
        "category": "Condo", "zone": "central_west",
        "lat": 1.3075, "lng": 103.7910,
        "address": "8 Biopolis Dr, Singapore 138622",
        "street": "Biopolis Dr", "district": "Buona Vista", "city": "Singapore", "country": "SG",
        "npc": "BV-NPC", "postal_code": "138622",
        "building_type": "condominium", "total_floors": 18, "total_units": 150, "year_built": 2020, "has_elevator": True,
        "description": "Biopolis 科技园旁高端公寓，步行 2 分钟到 Buona Vista MRT。NUS 和科技园区白领首选。",
        "building_amenities": ["健身房", "泳池", "自习室", "24小时安保", "电梯", "停车位", "网球场", "门禁系统", "快递代收"],
        "poi_zone": "buona_vista", "mrt_proximity": "near", "target_uni": "NUS", "uni_id": 1, "uni_proximity": "near",
        "commute": {"transit_min": 10, "walk_min": 22, "drive_min": 5},
        "unit_types": [
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("20"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "智能门锁"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("28"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "阳台", "微波炉", "冰箱", "智能门锁"]},
            {"type": "1bed", "tier": "standard", "area_sqm": Decimal("40"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "智能门锁"]},
            {"type": "1bed", "tier": "premium", "area_sqm": Decimal("52"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "阳台", "洗衣机", "冰箱", "电视", "智能门锁"]},
            {"type": "2bed", "tier": "premium", "area_sqm": Decimal("68"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "阳台", "洗衣机", "冰箱", "电视", "智能门锁"]},
        ],
    },
    {
        "name": "Boon Lay Gardens", "name_cn": "文礼花园公寓", "abbreviation": "BLG",
        "category": "Condo", "zone": "west",
        "lat": 1.3355, "lng": 103.7055,
        "address": "21 Boon Lay Dr, Singapore 649877",
        "street": "Boon Lay Dr", "district": "Boon Lay", "city": "Singapore", "country": "SG",
        "npc": "BL-NPC", "postal_code": "649877",
        "building_type": "condominium", "total_floors": 15, "total_units": 120, "year_built": 2017, "has_elevator": True,
        "description": "文礼地铁站旁中端公寓，紧邻 Jurong Point 购物中心。NTU 学生性价比之选。",
        "building_amenities": ["健身房", "泳池", "洗衣房", "24小时安保", "电梯", "停车位", "门禁系统"],
        "poi_zone": "boon_lay", "mrt_proximity": "near", "target_uni": "NTU", "uni_id": 2, "uni_proximity": "mid",
        "commute": {"transit_min": 20, "walk_min": 40, "drive_min": 8},
        "unit_types": [
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("18"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("25"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "阳台", "洗衣机", "冰箱"]},
            {"type": "1bed", "tier": "standard", "area_sqm": Decimal("35"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌"]},
            {"type": "1bed", "tier": "premium", "area_sqm": Decimal("45"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "阳台", "洗衣机", "冰箱", "电视"]},
        ],
    },
    {
        "name": "Lakeside Tower Condominium", "name_cn": "湖畔尚苑公寓", "abbreviation": "LST",
        "category": "Condo", "zone": "west",
        "lat": 1.3458, "lng": 103.7210,
        "address": "38 Yuan Ching Rd, Singapore 618653",
        "street": "Yuan Ching Rd", "district": "Lakeside", "city": "Singapore", "country": "SG",
        "npc": "LS-NPC", "postal_code": "618653",
        "building_type": "condominium", "total_floors": 12, "total_units": 90, "year_built": 2015, "has_elevator": True,
        "description": "裕廊湖畔宁静公寓，步行 5 分钟到 Lakeside MRT。NTU 学生偏爱之选。",
        "building_amenities": ["泳池", "自习室", "洗衣房", "24小时安保", "电梯", "停车位", "门禁系统", "BBQ区"],
        "poi_zone": "lakeside", "mrt_proximity": "mid", "target_uni": "NTU", "uni_id": 2, "uni_proximity": "mid",
        "commute": {"transit_min": 18, "walk_min": 45, "drive_min": 8},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("22"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "阳台", "衣柜", "智能门锁"]},
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("28"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱"]},
        ],
    },

    # ═══ SG: HDB 单间型 ═══
    {
        "name": "Dover Park HDB", "name_cn": "杜佛园组屋", "abbreviation": "DPH",
        "category": "HDB", "zone": "central_west",
        "lat": 1.3048, "lng": 103.7790,
        "address": "Blk 28 Dover Crescent, Singapore 130028",
        "street": "Dover Crescent", "district": "Dover", "city": "Singapore", "country": "SG",
        "npc": "DV-NPC", "postal_code": "130028",
        "building_type": "HDB", "total_floors": 12, "total_units": 96, "year_built": 2005, "has_elevator": True,
        "description": "Dover Crescent 组屋，距 NUS 一站公交。",
        "building_amenities": ["电梯", "洗衣房", "门禁系统"],
        "poi_zone": "dover", "mrt_proximity": "mid", "target_uni": "NUS", "uni_id": 1, "uni_proximity": "mid",
        "commute": {"transit_min": 18, "walk_min": 35, "drive_min": 8},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "衣柜", "智能门锁", "禁烟房"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "master", "tier": "premium", "area_sqm": Decimal("22"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "阳台", "电视", "智能门锁"]},
        ],
    },
    {
        "name": "West Coast Lodge HDB", "name_cn": "西海岸花园组屋", "abbreviation": "WCL",
        "category": "HDB", "zone": "central_west",
        "lat": 1.3105, "lng": 103.7545,
        "address": "Blk 712 Clementi West St 2, Singapore 120712",
        "street": "Clementi West St 2", "district": "West Coast", "city": "Singapore", "country": "SG",
        "npc": "WC-NPC", "postal_code": "120712",
        "building_type": "HDB", "total_floors": 10, "total_units": 80, "year_built": 1998, "has_elevator": True,
        "description": "西海岸组屋，NUS 2km，价格亲民。",
        "building_amenities": ["电梯", "洗衣房"],
        "poi_zone": "west_coast", "mrt_proximity": "far", "target_uni": "NUS", "uni_id": 1, "uni_proximity": "mid",
        "commute": {"transit_min": 25, "walk_min": 45, "drive_min": 10},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("9"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("13"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "衣柜", "禁烟房"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("15"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌"]},
        ],
    },
    {
        "name": "Jurong West Central HDB", "name_cn": "裕廊西中心组屋", "abbreviation": "JWC",
        "category": "HDB", "zone": "west",
        "lat": 1.3410, "lng": 103.7095,
        "address": "Blk 654 Jurong West St 61, Singapore 640654",
        "street": "Jurong West St 61", "district": "Jurong West", "city": "Singapore", "country": "SG",
        "npc": "JW-NPC", "postal_code": "640654",
        "building_type": "HDB", "total_floors": 16, "total_units": 128, "year_built": 2008, "has_elevator": True,
        "description": "裕廊西成熟社区，公交直达 NTU。",
        "building_amenities": ["电梯", "停车位"],
        "poi_zone": "jurong_west", "mrt_proximity": "mid", "target_uni": "NTU", "uni_id": 2, "uni_proximity": "mid",
        "commute": {"transit_min": 25, "walk_min": 50, "drive_min": 12},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("9"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("13"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "衣柜", "智能门锁"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "master", "tier": "premium", "area_sqm": Decimal("20"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "电视", "智能门锁"]},
        ],
    },

    # ═══ SG: 其它 ═══
    {
        "name": "Kallang River HDB", "name_cn": "加冷河畔组屋", "abbreviation": "KRH",
        "category": "HDB", "zone": "city_fringe",
        "lat": 1.3105, "lng": 103.8705,
        "address": "Blk 117 Jalan Besar, Singapore 208835",
        "street": "Jalan Besar", "district": "Kallang", "city": "Singapore", "country": "SG",
        "npc": "KL-NPC", "postal_code": "208835",
        "building_type": "HDB", "total_floors": 14, "total_units": 112, "year_built": 2010, "has_elevator": True,
        "description": "加冷组屋，2 站到 Bugis/SMU。",
        "building_amenities": ["电梯", "停车位", "洗衣房", "快递代收"],
        "poi_zone": "kallang", "mrt_proximity": "mid", "target_uni": "SMU", "uni_id": 3, "uni_proximity": "mid",
        "commute": {"transit_min": 15, "walk_min": 30, "drive_min": 7},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "衣柜", "可做饭", "智能门锁"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("17"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "master", "tier": "premium", "area_sqm": Decimal("22"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "阳台", "电视", "洗衣机"]},
        ],
    },
    {
        "name": "Lavender Court HDB", "name_cn": "劳明达苑组屋", "abbreviation": "LVC",
        "category": "HDB", "zone": "city_fringe",
        "lat": 1.3058, "lng": 103.8605,
        "address": "Blk 808 French Rd, Singapore 200808",
        "street": "French Rd", "district": "Lavender", "city": "Singapore", "country": "SG",
        "npc": "LV-NPC", "postal_code": "200808",
        "building_type": "HDB", "total_floors": 20, "total_units": 160, "year_built": 2012, "has_elevator": True,
        "description": "劳明达组屋，近 City Square Mall，SMU 高性价比选择。",
        "building_amenities": ["电梯", "停车位", "洗衣房", "门禁系统"],
        "poi_zone": "lavender", "mrt_proximity": "near", "target_uni": "SMU", "uni_id": 3, "uni_proximity": "mid",
        "commute": {"transit_min": 12, "walk_min": 25, "drive_min": 5},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "禁烟房"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("15"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "衣柜", "可做饭", "智能门锁"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("18"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "master", "tier": "premium", "area_sqm": Decimal("24"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "阳台", "电视", "洗衣机", "冰箱"]},
        ],
    },
    {
        "name": "Pioneer Student Residence", "name_cn": "先驱学生公寓", "abbreviation": "PSR",
        "category": "HDB", "zone": "west",
        "lat": 1.3385, "lng": 103.6965,
        "address": "55 Pioneer Sector, Singapore 628400",
        "street": "Pioneer Sector", "district": "Pioneer", "city": "Singapore", "country": "SG",
        "npc": "PN-NPC", "postal_code": "628400",
        "building_type": "student_hostel", "total_floors": 8, "total_units": 120, "year_built": 2014, "has_elevator": True,
        "description": "NTU 校门口学生公寓，Pioneer MRT 步行 2 分钟。",
        "building_amenities": ["自习室", "洗衣房", "24小时安保", "电梯", "校车接驳", "门禁系统", "快递代收"],
        "poi_zone": "pioneer", "mrt_proximity": "near", "target_uni": "NTU", "uni_id": 2, "uni_proximity": "near",
        "commute": {"transit_min": 8, "walk_min": 15, "drive_min": 4},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("12"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "禁烟房"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("18"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "阳台", "微波炉", "冰箱", "智能门锁"]},
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("14"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"],
             "label_override": "双人套间 (Ensuite Double)"},
        ],
    },
    {
        "name": "Woodlands Budget Hostel", "name_cn": "兀兰经济公寓", "abbreviation": "WBH",
        "category": "HDB", "zone": "suburb",
        "lat": 1.4420, "lng": 103.7860,
        "address": "Blk 888 Woodlands Dr 50, Singapore 730888",
        "street": "Woodlands Dr 50", "district": "Woodlands", "city": "Singapore", "country": "SG",
        "npc": "WD-NPC", "postal_code": "730888",
        "building_type": "HDB", "total_floors": 11, "total_units": 88, "year_built": 2000, "has_elevator": True,
        "description": "兀兰经济型住宿，价格极低，适合预算紧张的学生。",
        "building_amenities": ["电梯", "洗衣房", "快递代收"],
        "poi_zone": "woodlands", "mrt_proximity": "far", "target_uni": "NTU", "uni_id": 2, "uni_proximity": "far",
        "commute": {"transit_min": 55, "walk_min": 90, "drive_min": 25},
        "unit_types": [
            {"type": "shared", "tier": "standard", "area_sqm": Decimal("8"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌"]},
            {"type": "shared", "tier": "standard", "area_sqm": Decimal("12"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "衣柜", "禁烟房"],
             "label_override": "四人合租房"},
            {"type": "common", "tier": "standard", "area_sqm": Decimal("9"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "书桌", "可做饭"]},
        ],
    },
    {
        "name": "Bugis Central Suites", "name_cn": "武吉士中央公馆", "abbreviation": "BCS",
        "category": "Condo", "zone": "city",
        "lat": 1.2998, "lng": 103.8558,
        "address": "33 Victoria St, Singapore 188020",
        "street": "Victoria St", "district": "Bugis", "city": "Singapore", "country": "SG",
        "npc": "BG-NPC", "postal_code": "188020",
        "building_type": "condominium", "total_floors": 30, "total_units": 240, "year_built": 2021, "has_elevator": True,
        "description": "武吉士核心区高端公寓，SMU 步行 5 分钟到校。",
        "building_amenities": ["健身房", "泳池", "自习室", "洗衣房", "24小时安保", "电梯", "停车位", "网球场", "BBQ区", "门禁系统", "快递代收"],
        "poi_zone": "bugis", "mrt_proximity": "near", "target_uni": "SMU", "uni_id": 3, "uni_proximity": "near",
        "commute": {"transit_min": 5, "walk_min": 10, "drive_min": 3},
        "unit_types": [
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("25"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "阳台", "洗衣机", "冰箱", "智能门锁"]},
            {"type": "1bed", "tier": "standard", "area_sqm": Decimal("42"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "洗衣机", "智能门锁"]},
            {"type": "1bed", "tier": "premium", "area_sqm": Decimal("55"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "阳台", "洗衣机", "冰箱", "电视", "智能门锁"]},
            {"type": "2bed", "tier": "standard", "area_sqm": Decimal("65"),
             "amenities": ["空调", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "阳台", "洗衣机", "冰箱", "电视"]},
        ],
    },

    # ═══════════════════════════════════════════════════
    # London — 20 Institutes, GBP/周，聚焦 UCL/Imperial/LSE/KCL/UAL
    # ═══════════════════════════════════════════════════

    # ── UCL 周边 (5 栋) ──
    {
        "name": "Bloomsbury Central PBSA", "name_cn": "布鲁姆斯伯里学生公寓", "abbreviation": "BLM",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.5238, "lng": -0.1250,
        "address": "23-27 Woburn Place, London WC1H 0LU",
        "street": "Woburn Place", "district": "Bloomsbury", "city": "London", "postal_code": "WC1H 0LU",
        "building_type": "pbsa", "total_floors": 12, "total_units": 250, "year_built": 2016, "has_elevator": True,
        "description": "Bloomsbury 核心，步行 5 分钟到 UCL 主校区和 Russell Square 地铁站。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统", "快递代收"],
        "poi_zone": "bloomsbury", "mrt_proximity": "near", "target_uni": "UCL", "uni_id": 22, "uni_proximity": "near",
        "commute": {"transit_min": 8, "walk_min": 10, "drive_min": 5},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双层玻璃"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("18"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床", "双层玻璃"]},
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("22"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱", "微波炉", "包Bill"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("28"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "洗衣机", "包Bill"]},
        ],
    },
    {
        "name": "Fitzrovia Studios", "name_cn": "菲茨罗维亚公寓", "abbreviation": "FTZ",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.5200, "lng": -0.1350,
        "address": "48 Charlotte Street, London W1T 2NS",
        "street": "Charlotte Street", "district": "Fitzrovia", "city": "London", "postal_code": "W1T 2NS",
        "building_type": "pbsa", "total_floors": 8, "total_units": 100, "year_built": 2018, "has_elevator": True,
        "description": "Fitzrovia 精品学生公寓，UCL 和 UAL 中间位置，步行 8 分钟到两校。Goodge Street 地铁站旁。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统"],
        "poi_zone": "fitzrovia", "mrt_proximity": "near", "target_uni": "UCL", "uni_id": 22, "uni_proximity": "near",
        "commute": {"transit_min": 8, "walk_min": 12, "drive_min": 5},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("22"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱", "微波炉", "包Bill"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("28"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "洗衣机", "包Bill"]},
            {"type": "1bed", "tier": "standard", "area_sqm": Decimal("36"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "洗衣机", "包Bill"]},
        ],
    },
    {
        "name": "King's Cross Residence", "name_cn": "国王十字学生公寓", "abbreviation": "KCX",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.5315, "lng": -0.1240,
        "address": "1 Granary Square, London N1C 4AB",
        "street": "Granary Square", "district": "King's Cross", "city": "London", "postal_code": "N1C 4AB",
        "building_type": "pbsa", "total_floors": 10, "total_units": 180, "year_built": 2019, "has_elevator": True,
        "description": "紧邻 King's Cross 车站，UAL Central Saint Martins 隔壁，UCL 步行 15 分钟。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统"],
        "poi_zone": "kings_cross", "mrt_proximity": "near", "target_uni": "UAL", "uni_id": 29, "uni_proximity": "near",
        "commute": {"transit_min": 12, "walk_min": 20, "drive_min": 8},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("15"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("20"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床", "双层玻璃"]},
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("24"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱", "微波炉", "包Bill"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("30"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "洗衣机", "包Bill"]},
        ],
    },
    {
        "name": "Camden Town HMO", "name_cn": "卡姆登镇合租屋", "abbreviation": "CMD",
        "category": "HMO", "country": "GB", "zone": "zone2",
        "lat": 51.5390, "lng": -0.1430,
        "address": "27 Camden High Street, London NW1 7JE",
        "street": "Camden High Street", "district": "Camden", "city": "London", "postal_code": "NW1 7JE",
        "building_type": "hmo", "total_floors": 3, "total_units": 5, "year_built": 1910, "has_elevator": False,
        "description": "Camden Town 经典合租房，Northern Line 直达 UCL 仅 8 分钟。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "camden", "mrt_proximity": "near", "target_uni": "UCL", "uni_id": 22, "uni_proximity": "mid",
        "commute": {"transit_min": 12, "walk_min": 25, "drive_min": 8},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },
    {
        "name": "Angel HMO", "name_cn": "安吉尔合租屋", "abbreviation": "AGL",
        "category": "HMO", "country": "GB", "zone": "zone1",
        "lat": 51.5325, "lng": -0.1055,
        "address": "55 Upper Street, London N1 0NY",
        "street": "Upper Street", "district": "Angel", "city": "London", "postal_code": "N1 0NY",
        "building_type": "hmo", "total_floors": 3, "total_units": 4, "year_built": 1905, "has_elevator": False,
        "description": "Angel 合租房，Northern Line 直达 UCL (10min) 和 LSE (15min)。Upper Street 餐饮酒吧一条街。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "angel", "mrt_proximity": "near", "target_uni": "UCL", "uni_id": 22, "uni_proximity": "mid",
        "commute": {"transit_min": 12, "walk_min": 30, "drive_min": 8},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
        ],
    },

    # ── Imperial 周边 (5 栋) ──
    {
        "name": "South Ken Imperial Suites", "name_cn": "南肯辛顿帝国套房", "abbreviation": "SKN",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.4950, "lng": -0.1740,
        "address": "15 Harrington Road, London SW7 3ES",
        "street": "Harrington Road", "district": "South Kensington", "city": "London", "postal_code": "SW7 3ES",
        "building_type": "pbsa", "total_floors": 8, "total_units": 120, "year_built": 2014, "has_elevator": True,
        "description": "Imperial 南肯校区旁高端学生公寓，步行 3 分钟到 South Kensington 地铁站。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统", "快递代收"],
        "poi_zone": "south_kensington", "mrt_proximity": "near", "target_uni": "Imperial", "uni_id": 23, "uni_proximity": "near",
        "commute": {"transit_min": 5, "walk_min": 8, "drive_min": 4},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双层玻璃"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("18"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床", "双层玻璃", "包Bill"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("26"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "包Bill"]},
            {"type": "1bed", "tier": "standard", "area_sqm": Decimal("36"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "洗衣机", "包Bill"]},
        ],
    },
    {
        "name": "Earl's Court Studios", "name_cn": "伯爵阁公寓", "abbreviation": "ECT",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.4915, "lng": -0.1935,
        "address": "10 Hogarth Road, London SW5 0PT",
        "street": "Hogarth Road", "district": "Earl's Court", "city": "London", "postal_code": "SW5 0PT",
        "building_type": "pbsa", "total_floors": 6, "total_units": 80, "year_built": 2015, "has_elevator": True,
        "description": "Earl's Court 核心区，Piccadilly/District 双线。Imperial 南肯步行 12 分钟。",
        "building_amenities": ["自习室", "洗衣房", "24小时安保", "电梯", "门禁系统"],
        "poi_zone": "earls_court", "mrt_proximity": "near", "target_uni": "Imperial", "uni_id": 23, "uni_proximity": "mid",
        "commute": {"transit_min": 10, "walk_min": 15, "drive_min": 6},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("13"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("17"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("22"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱", "微波炉"]},
        ],
    },
    {
        "name": "Gloucester Road PBSA", "name_cn": "格洛斯特路学生公寓", "abbreviation": "GLR",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.4950, "lng": -0.1830,
        "address": "42 Gloucester Road, London SW7 4QT",
        "street": "Gloucester Road", "district": "Kensington", "city": "London", "postal_code": "SW7 4QT",
        "building_type": "pbsa", "total_floors": 10, "total_units": 150, "year_built": 2014, "has_elevator": True,
        "description": "Gloucester Road 旁学生公寓，District/Circle/Piccadilly 三线。Imperial 步行 10 分钟。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统"],
        "poi_zone": "gloucester_road", "mrt_proximity": "near", "target_uni": "Imperial", "uni_id": 23, "uni_proximity": "mid",
        "commute": {"transit_min": 8, "walk_min": 12, "drive_min": 5},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("18"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床", "双层玻璃", "包Bill"]},
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("24"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱", "微波炉", "包Bill"]},
        ],
    },
    {
        "name": "Hammersmith Shared Living", "name_cn": "汉默史密斯合租公寓", "abbreviation": "HMM",
        "category": "HMO", "country": "GB", "zone": "zone2",
        "lat": 51.4930, "lng": -0.2250,
        "address": "42 Talgarth Road, London W6 8BJ",
        "street": "Talgarth Road", "district": "Hammersmith", "city": "London", "postal_code": "W6 8BJ",
        "building_type": "hmo", "total_floors": 3, "total_units": 5, "year_built": 1920, "has_elevator": False,
        "description": "Hammersmith 维多利亚式合租房，Imperial 学生步行 15 分钟。Piccadilly/District 直达市中心。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "hammersmith", "mrt_proximity": "near", "target_uni": "Imperial", "uni_id": 23, "uni_proximity": "mid",
        "commute": {"transit_min": 12, "walk_min": 20, "drive_min": 8},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },
    {
        "name": "Shepherd's Bush HMO", "name_cn": "牧羊丛合租屋", "abbreviation": "SHB",
        "category": "HMO", "country": "GB", "zone": "zone2",
        "lat": 51.5055, "lng": -0.2215,
        "address": "7 Uxbridge Road, London W12 8LJ",
        "street": "Uxbridge Road", "district": "Shepherd's Bush", "city": "London", "postal_code": "W12 8LJ",
        "building_type": "hmo", "total_floors": 3, "total_units": 5, "year_built": 1900, "has_elevator": False,
        "description": "Shepherd's Bush 合租房，Central/Circle/H&C 三线。Westfield London 步行 5 分钟。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "shepherds_bush", "mrt_proximity": "near", "target_uni": "Imperial", "uni_id": 23, "uni_proximity": "mid",
        "commute": {"transit_min": 15, "walk_min": 30, "drive_min": 10},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("13"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },

    # ── LSE / KCL 周边 (7 栋) ──
    {
        "name": "Holborn Strand Studios", "name_cn": "霍尔本斯特兰德公寓", "abbreviation": "HLB",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.5160, "lng": -0.1170,
        "address": "88 Kingsway, London WC2B 6AA",
        "street": "Kingsway", "district": "Holborn", "city": "London", "postal_code": "WC2B 6AA",
        "building_type": "pbsa", "total_floors": 14, "total_units": 200, "year_built": 2018, "has_elevator": True,
        "description": "LSE 和 KCL 学生首选 Holborn 核心区公寓。步行 5 分钟到两校。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统", "快递代收", "BBQ区"],
        "poi_zone": "holborn", "mrt_proximity": "near", "target_uni": "LSE", "uni_id": 24, "uni_proximity": "near",
        "commute": {"transit_min": 6, "walk_min": 10, "drive_min": 4},
        "unit_types": [
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("20"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱", "微波炉", "双层玻璃", "包Bill"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("28"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "洗衣机", "阳台", "双层玻璃", "包Bill"]},
            {"type": "1bed", "tier": "standard", "area_sqm": Decimal("35"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "洗衣机", "双层玻璃", "包Bill"]},
        ],
    },
    {
        "name": "Waterloo HMO", "name_cn": "滑铁卢合租屋", "abbreviation": "WLO",
        "category": "HMO", "country": "GB", "zone": "zone1",
        "lat": 51.5035, "lng": -0.1120,
        "address": "12 Cornwall Road, London SE1 8TQ",
        "street": "Cornwall Road", "district": "Waterloo", "city": "London", "postal_code": "SE1 8TQ",
        "building_type": "hmo", "total_floors": 4, "total_units": 6, "year_built": 1920, "has_elevator": False,
        "description": "Waterloo 核心区合租房，步行 8 分钟到 KCL Waterloo 校区，10 分钟到 LSE。South Bank 文化区。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "waterloo", "mrt_proximity": "near", "target_uni": "KCL", "uni_id": 25, "uni_proximity": "near",
        "commute": {"transit_min": 8, "walk_min": 12, "drive_min": 5},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("17"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },
    {
        "name": "London Bridge HMO", "name_cn": "伦敦桥合租屋", "abbreviation": "LNB",
        "category": "HMO", "country": "GB", "zone": "zone1",
        "lat": 51.5050, "lng": -0.0860,
        "address": "25 Borough High Street, London SE1 1NH",
        "street": "Borough High Street", "district": "London Bridge", "city": "London", "postal_code": "SE1 1NH",
        "building_type": "hmo", "total_floors": 4, "total_units": 5, "year_built": 1930, "has_elevator": False,
        "description": "London Bridge 合租房，KCL Guy's 校区步行 2 分钟。Borough Market 美食天堂。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "london_bridge", "mrt_proximity": "near", "target_uni": "KCL", "uni_id": 25, "uni_proximity": "near",
        "commute": {"transit_min": 5, "walk_min": 8, "drive_min": 4},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("11"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("15"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("18"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
        ],
    },
    {
        "name": "Temple Studios", "name_cn": "坦普尔公寓", "abbreviation": "TMP",
        "category": "PBSA", "country": "GB", "zone": "zone1",
        "lat": 51.5110, "lng": -0.1110,
        "address": "3 Arundel Street, London WC2R 3DX",
        "street": "Arundel Street", "district": "Temple", "city": "London", "postal_code": "WC2R 3DX",
        "building_type": "pbsa", "total_floors": 12, "total_units": 160, "year_built": 2019, "has_elevator": True,
        "description": "Temple 核心区学生公寓，LSE 和 KCL Strand 校区步行 3 分钟。泰晤士河畔绝佳位置。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统", "快递代收"],
        "poi_zone": "holborn", "mrt_proximity": "near", "target_uni": "LSE", "uni_id": 24, "uni_proximity": "near",
        "commute": {"transit_min": 5, "walk_min": 8, "drive_min": 4},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双层玻璃"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("18"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床", "双层玻璃", "包Bill"]},
            {"type": "studio", "tier": "premium", "area_sqm": Decimal("26"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "双人床", "冰箱", "微波炉", "包Bill"]},
        ],
    },
    {
        "name": "Pimlico HMO", "name_cn": "皮姆利科合租屋", "abbreviation": "PMC",
        "category": "HMO", "country": "GB", "zone": "zone1",
        "lat": 51.4895, "lng": -0.1340,
        "address": "30 Warwick Way, London SW1V 1RY",
        "street": "Warwick Way", "district": "Pimlico", "city": "London", "postal_code": "SW1V 1RY",
        "building_type": "hmo", "total_floors": 4, "total_units": 5, "year_built": 1890, "has_elevator": False,
        "description": "Pimlico 合租房，Victoria Line 直达 Oxford Circus。LSE 和 Imperial 中间位置，性价比之选。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "pimlico", "mrt_proximity": "near", "target_uni": "LSE", "uni_id": 24, "uni_proximity": "mid",
        "commute": {"transit_min": 12, "walk_min": 25, "drive_min": 8},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },
    {
        "name": "Bermondsey HMO", "name_cn": "伯蒙德赛合租屋", "abbreviation": "BRM",
        "category": "HMO", "country": "GB", "zone": "zone2",
        "lat": 51.4975, "lng": -0.0650,
        "address": "45 Jamaica Road, London SE16 4RT",
        "street": "Jamaica Road", "district": "Bermondsey", "city": "London", "postal_code": "SE16 4RT",
        "building_type": "hmo", "total_floors": 3, "total_units": 4, "year_built": 1930, "has_elevator": False,
        "description": "Bermondsey 合租房，Jubilee Line 直达 London Bridge (KCL Guy's) 仅 5 分钟。",
        "building_amenities": ["洗衣房"],
        "poi_zone": "bermondsey", "mrt_proximity": "mid", "target_uni": "KCL", "uni_id": 25, "uni_proximity": "mid",
        "commute": {"transit_min": 12, "walk_min": 25, "drive_min": 8},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("9"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("13"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("15"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },
    {
        "name": "Brixton HMO", "name_cn": "布里克顿合租屋", "abbreviation": "BRX",
        "category": "HMO", "country": "GB", "zone": "zone2",
        "lat": 51.4620, "lng": -0.1130,
        "address": "33 Brixton Hill, London SW2 1AA",
        "street": "Brixton Hill", "district": "Brixton", "city": "London", "postal_code": "SW2 1AA",
        "building_type": "hmo", "total_floors": 3, "total_units": 5, "year_built": 1920, "has_elevator": False,
        "description": "Brixton 合租房，Victoria Line 直达 Victoria/Warren Street。Brixton Village 美食市场。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "brixton", "mrt_proximity": "near", "target_uni": "LSE", "uni_id": 24, "uni_proximity": "mid",
        "commute": {"transit_min": 15, "walk_min": 40, "drive_min": 12},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("16"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },

    # ── UAL 周边 (3 栋) ──
    {
        "name": "Shoreditch HMO", "name_cn": "肖尔迪奇合租屋", "abbreviation": "SHD",
        "category": "HMO", "country": "GB", "zone": "zone1",
        "lat": 51.5250, "lng": -0.0800,
        "address": "18 Great Eastern Street, London EC2A 3EJ",
        "street": "Great Eastern Street", "district": "Shoreditch", "city": "London", "postal_code": "EC2A 3EJ",
        "building_type": "hmo", "total_floors": 3, "total_units": 4, "year_built": 1935, "has_elevator": False,
        "description": "Shoreditch 创意区合租房，UAL LCF 步行 10 分钟。东伦敦潮流中心。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "shoreditch", "mrt_proximity": "mid", "target_uni": "UAL", "uni_id": 29, "uni_proximity": "mid",
        "commute": {"transit_min": 12, "walk_min": 20, "drive_min": 8},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("15"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜"]},
        ],
    },
    {
        "name": "Chelsea HMO", "name_cn": "切尔西合租屋", "abbreviation": "CLS",
        "category": "HMO", "country": "GB", "zone": "zone1",
        "lat": 51.4900, "lng": -0.1630,
        "address": "22 King's Road, London SW3 4UD",
        "street": "King's Road", "district": "Chelsea", "city": "London", "postal_code": "SW3 4UD",
        "building_type": "hmo", "total_floors": 4, "total_units": 5, "year_built": 1880, "has_elevator": False,
        "description": "Chelsea 经典合租房，UAL Chelsea 校区步行 5 分钟。King's Road 购物品味街区。",
        "building_amenities": ["洗衣房", "WiFi免费"],
        "poi_zone": "chelsea", "mrt_proximity": "mid", "target_uni": "UAL", "uni_id": 29, "uni_proximity": "near",
        "commute": {"transit_min": 10, "walk_min": 15, "drive_min": 6},
        "unit_types": [
            {"type": "common", "tier": "standard", "area_sqm": Decimal("10"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜"]},
            {"type": "common", "tier": "premium", "area_sqm": Decimal("14"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "书桌", "衣柜", "双人床", "包Bill"]},
            {"type": "master", "tier": "standard", "area_sqm": Decimal("17"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床"]},
        ],
    },
    {
        "name": "Elephant Park PBSA", "name_cn": "象堡花园学生公寓", "abbreviation": "ELP",
        "category": "PBSA", "country": "GB", "zone": "zone2",
        "lat": 51.4935, "lng": -0.0985,
        "address": "10 Elephant Road, London SE17 1LB",
        "street": "Elephant Road", "district": "Elephant & Castle", "city": "London", "postal_code": "SE17 1LB",
        "building_type": "new_build", "total_floors": 18, "total_units": 150, "year_built": 2020, "has_elevator": True,
        "description": "Elephant & Castle 新兴社区，UAL London College of Communication 步行 5 分钟。Northern/Bakerloo 双线。",
        "building_amenities": ["健身房", "自习室", "洗衣房", "24小时安保", "电梯", "门禁系统"],
        "poi_zone": "angel", "mrt_proximity": "near", "target_uni": "UAL", "uni_id": 29, "uni_proximity": "near",
        "commute": {"transit_min": 8, "walk_min": 12, "drive_min": 5},
        "unit_types": [
            {"type": "ensuite", "tier": "standard", "area_sqm": Decimal("15"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双层玻璃"]},
            {"type": "ensuite", "tier": "premium", "area_sqm": Decimal("19"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "书桌", "衣柜", "双人床", "双层玻璃", "包Bill"]},
            {"type": "studio", "tier": "standard", "area_sqm": Decimal("24"),
             "amenities": ["暖气", "WiFi免费", "家具齐全", "独立卫浴", "独立厨房", "书桌", "冰箱", "微波炉", "双层玻璃", "包Bill"]},
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════
# 数据库操作
# ═══════════════════════════════════════════════════════════════════

ROOM_TYPE_LABELS: dict[str, str] = {
    "studio": "单人Studio", "1bed": "一室一厅", "2bed": "两室一厅",
    "3bed": "三室两卫", "ensuite": "独卫套间", "master": "主卧套间",
    "common": "普通单间", "shared": "合租床位",
}

ROOM_TYPE_TO_PROPERTY_TYPE: dict[str, str] = {
    "studio": "studio", "1bed": "1bed", "2bed": "2bed", "3bed": "3bed",
    "ensuite": "ensuite", "master": "ensuite", "common": "shared", "shared": "shared",
}


async def _get_or_create_admin(session) -> int:
    result = await session.execute(select(User).where(User.username == "admin").limit(1))
    admin = result.scalar_one_or_none()
    if admin:
        return admin.id
    admin = User(username="admin", email="admin@rental-housing.local",
                 password_hash="$2b$12$placeholder",
                 role=UserRole.admin, status=UserStatus.active)
    session.add(admin)
    await session.flush()
    return admin.id


# 与 INSTITUTE_CONFIGS 中的 uni_id 保持一致，先写入被 commute 外键引用的大学。
UNIVERSITY_SEEDS = [
    {"id": 1, "name": "National University of Singapore", "name_cn": "新加坡国立大学", "abbreviation": "NUS", "city": "Singapore", "country": "SG", "latitude": 1.2966, "longitude": 103.7764, "is_hot": True},
    {"id": 2, "name": "Nanyang Technological University", "name_cn": "南洋理工大学", "abbreviation": "NTU", "city": "Singapore", "country": "SG", "latitude": 1.3483, "longitude": 103.6831, "is_hot": True},
    {"id": 3, "name": "Singapore Management University", "name_cn": "新加坡管理大学", "abbreviation": "SMU", "city": "Singapore", "country": "SG", "latitude": 1.2966, "longitude": 103.8500, "is_hot": True},
    {"id": 22, "name": "University College London", "name_cn": "伦敦大学学院", "abbreviation": "UCL", "city": "London", "country": "GB", "latitude": 51.5246, "longitude": -0.1340, "is_hot": True},
    {"id": 23, "name": "Imperial College London", "name_cn": "帝国理工学院", "abbreviation": "Imperial", "city": "London", "country": "GB", "latitude": 51.4988, "longitude": -0.1749, "is_hot": True},
    {"id": 24, "name": "London School of Economics", "name_cn": "伦敦政治经济学院", "abbreviation": "LSE", "city": "London", "country": "GB", "latitude": 51.5145, "longitude": -0.1166, "is_hot": True},
    {"id": 25, "name": "King's College London", "name_cn": "伦敦国王学院", "abbreviation": "KCL", "city": "London", "country": "GB", "latitude": 51.5115, "longitude": -0.1160, "is_hot": True},
    {"id": 29, "name": "University of the Arts London", "name_cn": "伦敦艺术大学", "abbreviation": "UAL", "city": "London", "country": "GB", "latitude": 51.5210, "longitude": -0.1300, "is_hot": True},
]


async def _seed_universities(session) -> None:
    for data in UNIVERSITY_SEEDS:
        if await session.get(University, data["id"]) is None:
            session.add(University(**data, is_active=True))
    await session.flush()


def _make_unit_type_name(cfg: dict) -> str:
    if "label_override" in cfg:
        return cfg["label_override"]
    base = ROOM_TYPE_LABELS.get(cfg["type"], cfg["type"])
    tier = "高级" if cfg["tier"] == "premium" else "标准"
    return f"{base}（{tier}）"


async def seed(clear_existing: bool = False) -> None:
    async with async_session_maker() as session:
        if clear_existing:
            print("清除现有数据...")
            await session.execute(delete(InstituteCommute))
            await session.execute(delete(InstitutePOI))
            # Delete dependent child tables first
            await session.execute(text("DELETE FROM booking_flow_drafts WHERE unit_type_id IN (SELECT id FROM unit_types WHERE institute_id IN (SELECT id FROM institutes WHERE country='SG'))"))
            await session.execute(text("DELETE FROM agent_cart_items WHERE unit_type_id IN (SELECT id FROM unit_types WHERE institute_id IN (SELECT id FROM institutes WHERE country='SG'))"))
            await session.execute(text("DELETE FROM user_favorites WHERE unit_type_id IN (SELECT id FROM unit_types WHERE institute_id IN (SELECT id FROM institutes WHERE country='SG'))"))
            await session.execute(text("DELETE FROM compare_sessions"))  # references unit_type_ids JSON
            await session.execute(delete(UnitType).where(
                UnitType.institute_id.in_(select(Institute.id).where(Institute.country == "SG"))
            ))
            await session.execute(delete(Institute).where(Institute.country == "SG"))
            await session.commit()
            print("已清除新加坡数据")

        admin_id = await _get_or_create_admin(session)
        await _seed_universities(session)
        total_ut = 0
        summary_rows: list[dict] = []

        for cfg in INSTITUTE_CONFIGS:
            inst = Institute(
                name=cfg["name"], name_cn=cfg["name_cn"], abbreviation=cfg["abbreviation"],
                address=cfg["address"], street=cfg.get("street"),
                district=cfg.get("district"), city=cfg.get("city"),
                country=cfg.get("country", "SG"),
                npc=cfg.get("npc"), postal_code=cfg.get("postal_code"),
                latitude=Decimal(str(cfg["lat"])), longitude=Decimal(str(cfg["lng"])),
                building_type=cfg.get("building_type"),
                total_floors=cfg.get("total_floors"), total_units=cfg.get("total_units"),
                year_built=cfg.get("year_built"), has_elevator=cfg.get("has_elevator", False),
                amenities=cfg.get("building_amenities", []),
                description=cfg.get("description"), status=InstituteStatus.active,
                created_by=admin_id,
            )
            session.add(inst)
            await session.flush()

            country_code = cfg.get("country", "SG")
            unit_prices: list[Decimal] = []
            for ut_cfg in cfg["unit_types"]:
                price, breakdown = compute_price(
                    room_type=ut_cfg["type"], zone=cfg["zone"],
                    mrt_proximity=cfg["mrt_proximity"], uni_proximity=cfg["uni_proximity"],
                    room_amenities=ut_cfg["amenities"], country=country_code,
                )
                unit_prices.append(price)
                currency_code = "GBP" if country_code == "GB" else "SGD"
                ut = UnitType(
                    institute_id=inst.id, name=_make_unit_type_name(ut_cfg),
                    property_type=ROOM_TYPE_TO_PROPERTY_TYPE.get(ut_cfg["type"], "shared"),
                    bedrooms=_guess_bedrooms(ut_cfg["type"]),
                    bathrooms=2 if ut_cfg["type"] in ("2bed", "3bed") else 1,
                    hall_count=0, area_sqm=ut_cfg.get("area_sqm"), base_rent=price,
                    deposit_type=DepositType.one_month, deposit_amount=int(price),
                    currency=currency_code, amenities=ut_cfg["amenities"],
                    available_from=date.today(),
                    min_stay_months=3 if ut_cfg["type"] != "shared" else 1,
                    status=UnitTypeStatus.available,
                    total_count=_guess_total_count(ut_cfg["type"], cfg["category"]),
                    available_count=_guess_available_count(ut_cfg["type"], cfg["category"]),
                    has_vacancy=True,
                )
                session.add(ut)
                total_ut += 1
            await session.flush()

            card_price = min(unit_prices)
            cur = chr(163) if country_code == "GB" else "S$"  # £ or S$
            summary_rows.append({
                "name": cfg["name_cn"], "cat": cfg["category"], "zone": cfg["zone"],
                "mrt": cfg["mrt_proximity"], "uni": cfg["uni_proximity"],
                "uts": len(cfg["unit_types"]),
                "card": f"{cur}{card_price}",
                "range": f"{cur}{min(unit_prices)} - {cur}{max(unit_prices)}",
                "currency": cur,
            })

            # POI data
            poi_items = POI_TEMPLATES.get(cfg["poi_zone"], [])
            map_poi_data: dict[str, list] = {}
            for item in poi_items:
                cat = item["category"]
                if cat not in map_poi_data:
                    map_poi_data[cat] = []
                map_poi_data[cat].append({
                    "name": item["name"], "lat": item["lat"], "lng": item["lng"],
                    "distance_m": item["distance_m"],
                })
            await session.execute(
                text("INSERT INTO institute_pois (institute_id, content, poi_data, map_poi_data, safety_data, generated_at, reviewed) VALUES (:inst_id, :content, :poi_data, :map_poi, :safety, :gen_at, false) ON CONFLICT (institute_id) DO NOTHING"),
                {
                    "inst_id": inst.id,
                    "content": f"{cfg['name']} 周边设施",
                    "poi_data": json.dumps({"categories": list(map_poi_data.keys()), "total_pois": len(poi_items)}),
                    "map_poi": json.dumps(map_poi_data),
                    "safety": json.dumps({"crime_rate": "low"}),
                    "gen_at": datetime.now(timezone.utc),
                },
            )

            # Commute data
            commute = InstituteCommute(
                institute_id=inst.id, university_id=cfg["uni_id"],
                transit_min=cfg["commute"]["transit_min"],
                walk_min=cfg["commute"]["walk_min"],
                drive_min=cfg["commute"]["drive_min"],
                source="seed_script", computed_at=datetime.now(timezone.utc),
            )
            session.add(commute)

        await session.commit()

        print(f"\n{'=' * 120}")
        print(f"{'Institute':<24} {'类型':<8} {'区域':<14} {'MRT':<6} {'Uni':<6} {'户型':<5} {'卡片价':<12} {'价格区间'}")
        print("=" * 120)
        for r in summary_rows:
            print(f"{r['name']:<22} {r['cat']:<8} {r['zone']:<14} {r['mrt']:<6} {r['uni']:<6} {r['uts']:<5} {r['card']:<12} {r['range']}")
        print("=" * 120)
        print(f"\n总计: {len(summary_rows)} Institute, {total_ut} UnitType\n")


def _guess_bedrooms(rt: str) -> int:
    if rt == "2bed": return 2
    if rt == "3bed": return 3
    return 1


def _guess_total_count(rt: str, cat: str) -> int:
    if rt == "shared": return random.randint(4, 8)
    if rt == "common": return random.randint(3, 6)
    if rt == "master": return random.randint(2, 4)
    if rt == "ensuite": return random.randint(3, 10)
    return random.randint(1, 4)


def _guess_available_count(rt: str, cat: str) -> int:
    total = _guess_total_count(rt, cat)
    return max(1, total - random.randint(0, total // 2))


# ═══════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════

async def main():
    clear = "--clear" in sys.argv or "--clear-existing" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=" * 60)
        print("Dry-run: 前 3 个 Institute 定价明细")
        print("=" * 60)
        for cfg in INSTITUTE_CONFIGS[:3]:
            cc = cfg.get("country", "SG")
            sym = chr(163) if cc == "GB" else "S$"
            print(f"\n{cfg['name_cn']} | {cfg['category']} | {cfg['zone']} | MRT={cfg['mrt_proximity']} Uni={cfg['uni_proximity']}")
            for ut_cfg in cfg["unit_types"]:
                price, bd = compute_price(
                    room_type=ut_cfg["type"], zone=cfg["zone"],
                    mrt_proximity=cfg["mrt_proximity"], uni_proximity=cfg["uni_proximity"],
                    room_amenities=ut_cfg["amenities"], country=cc,
                )
                print(f"  {_make_unit_type_name(ut_cfg):<22} {sym}{price:<8} | 基准={sym}{bd.get('基准价',0)} 区位={bd.get('区位调整',0):+.2f} 配套+{sym}{bd.get('配套加价',0)} 抖动={bd.get('抖动',1)}")
        print("\n--dry-run 完成\n")
        return

    await seed(clear_existing=clear)
    print("种子数据写入完成\n")


if __name__ == "__main__":
    asyncio.run(main())

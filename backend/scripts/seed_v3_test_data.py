# -*- coding: utf-8 -*-
"""
种子数据脚本 v3 — 新加坡真实租金测试数据

设计理念：
  - 12 个 Institute（公寓/楼栋），分为 4 类：Condo整租型、HDB单间型、Ensuite学生公寓型、Shared经济型
  - 每个 Institute 的户型风格统一（如做 Condo 的不做 shared room）
  - 同户型内分 Standard / Premium 两个档次，通过设施差异体现价格
  - 搜索卡片展示价格 = 该 Institute 内最低 UnitType 的 base_rent
  - 定价基于 PropertyGuru / 99.co / HDB 2025 真实行情

运行方式：
  cd backend && .venv/Scripts/python.exe scripts/seed_v3_test_data.py
  cd backend && .venv/Scripts/python.exe scripts/seed_v3_test_data.py --clear
  cd backend && .venv/Scripts/python.exe scripts/seed_v3_test_data.py --dry-run
"""

import asyncio
import json
import os
import random
import sys
import uuid
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
# 定价常量
# ═══════════════════════════════════════════════════════════════════

# 房型市场基准价（SGD/月）—— 已隐含 Condo/HDB 差异
# 数据来源：PropertyGuru / Hozuko / 99.co 2025 年新加坡中位数
ROOM_TYPE_BASE: dict[str, Decimal] = {
    "shared":  Decimal("750"),    # 合租床位
    "common":  Decimal("950"),    # HDB 普通房
    "ensuite": Decimal("1250"),   # 学生公寓套间
    "master":  Decimal("1450"),   # HDB 主卧
    "studio":  Decimal("2400"),   # Condo Studio
    "1bed":    Decimal("2800"),   # Condo 一室
    "2bed":    Decimal("4200"),   # Condo 两室
    "3bed":    Decimal("5200"),   # Condo 三室
}

# 区位调整（加法型，避免乘法叠加失真）
# 每个因子相对于基准的百分比调整
ZONE_ADJ: dict[str, Decimal] = {
    "suburb":       Decimal("-0.10"),  # Woodlands 偏远
    "west":         Decimal("-0.04"),  # Jurong 西部
    "central_west": Decimal("+0.06"),  # Clementi / Buona Vista
    "city_fringe":  Decimal("+0.10"),  # Kallang / Lavender
    "city":         Decimal("+0.16"),  # Bugis 市中心
}

MRT_ADJ: dict[str, Decimal] = {
    "near":    Decimal("+0.08"),   # <400m
    "mid":     Decimal("+0.02"),   # 400-800m
    "far":     Decimal("-0.06"),   # >800m
}

UNI_ADJ: dict[str, Decimal] = {
    "near":    Decimal("+0.08"),   # <1km
    "mid":     Decimal("+0.02"),   # 1-3km
    "far":     Decimal("-0.04"),   # >3km
}

# ── 房内配套加价（S$/月）──
ROOM_AMENITY_ADDERS: dict[str, Decimal] = {
    "空调":       Decimal("30"),
    "独立卫浴":   Decimal("120"),
    "阳台":       Decimal("100"),
    "书桌":       Decimal("20"),
    "洗衣机":     Decimal("30"),
    "冰箱":       Decimal("20"),
    "WiFi免费":   Decimal("15"),
    "电视":       Decimal("20"),
    "微波炉":     Decimal("15"),
    "衣柜":       Decimal("15"),
    "独立厨房":   Decimal("80"),
    "可做饭":     Decimal("40"),
    "包水电":     Decimal("100"),
    "禁烟房":     Decimal("10"),
    "宠物友好":   Decimal("50"),
    "智能门锁":   Decimal("15"),
}

# ── 楼栋配套（仅信息展示，不加价）──
# 楼栋配套（健身房/泳池/安保等）已隐含在区域和房型基准中
# 对于 HDB 少量楼栋配套（如洗衣房/电梯），贡献极小，保留展示不使用
BUILDING_AMENITY_SHOW: set[str] = {
    "健身房", "泳池", "自习室", "洗衣房", "24小时安保",
    "电梯", "停车位", "网球场", "BBQ区", "校车接驳",
    "快递代收", "门禁系统",
}

# 家具齐全、精装修 → 基准配置，不加价
BASELINE_AMENITIES = {"家具齐全", "精装修"}

# ═══════════════════════════════════════════════════════════════════
# 价格计算
# ═══════════════════════════════════════════════════════════════════

def compute_price(
    room_type: str,
    zone: str,
    mrt_proximity: str,
    uni_proximity: str,
    room_amenities: list[str],
) -> tuple[Decimal, dict[str, Decimal]]:
    """计算最终月租。

    公式：price = (base × location_mult + amenity_adders) × jitter

    - base: 房型市场基准价（SGD）
    - location_mult: 1 + zone_adj + mrt_adj + uni_adj（加法型）
    - amenity_adders: 仅房内配套加价（楼栋配套已隐含在区位中）
    - jitter: ±5%
    """
    breakdown: dict[str, Decimal] = {}

    base = ROOM_TYPE_BASE.get(room_type, Decimal("1000"))
    breakdown["基准价"] = base

    # 区位调整（加法合成）
    zone_adj = ZONE_ADJ.get(zone, Decimal("0"))
    mrt_adj = MRT_ADJ.get(mrt_proximity, Decimal("0"))
    uni_adj = UNI_ADJ.get(uni_proximity, Decimal("0"))
    location_mult = Decimal("1.0") + zone_adj + mrt_adj + uni_adj

    breakdown["区位调整"] = zone_adj + mrt_adj + uni_adj

    price = base * location_mult
    breakdown["区位后价格"] = price

    # 仅房内配套加价
    adder_total = Decimal("0")
    for a in room_amenities:
        if a in ROOM_AMENITY_ADDERS:
            adder_total += ROOM_AMENITY_ADDERS[a]
    price += adder_total
    breakdown["配套加价"] = adder_total

    # 随机抖动 ±5%
    jitter = Decimal(str(round(random.uniform(0.95, 1.05), 4)))
    price *= jitter
    breakdown["抖动"] = jitter

    # 取整到 5 SGD
    price = Decimal(int(price / 5)) * 5

    return price, breakdown


# ═══════════════════════════════════════════════════════════════════
# POI 数据模板（新加坡真实地标）
# ═══════════════════════════════════════════════════════════════════

POI_TEMPLATES: dict[str, list[dict]] = {
    # ── Clementi ──
    "clementi": [
        {"category": "subway_station", "name": "Clementi MRT", "lat": 1.3150, "lng": 103.7645, "distance_m": 250},
        {"category": "bus_station", "name": "Clementi Bus Interchange", "lat": 1.3152, "lng": 103.7648, "distance_m": 280},
        {"category": "mall", "name": "Clementi Mall", "lat": 1.3153, "lng": 103.7650, "distance_m": 300},
        {"category": "supermarket", "name": "FairPrice Clementi", "lat": 1.3150, "lng": 103.7652, "distance_m": 320},
        {"category": "hawker_centre", "name": "Clementi 448 Market & Food Centre", "lat": 1.3140, "lng": 103.7630, "distance_m": 200},
        {"category": "restaurant", "name": "McDonald's Clementi", "lat": 1.3145, "lng": 103.7640, "distance_m": 180},
        {"category": "cafe", "name": "Starbucks Clementi Mall", "lat": 1.3150, "lng": 103.7650, "distance_m": 300},
        {"category": "hospital", "name": "National University Hospital", "lat": 1.2940, "lng": 103.7830, "distance_m": 2800},
        {"category": "pharmacy", "name": "Guardian Clementi", "lat": 1.3150, "lng": 103.7648, "distance_m": 290},
        {"category": "gym", "name": "Anytime Fitness Clementi", "lat": 1.3152, "lng": 103.7645, "distance_m": 300},
    ],
    # ── Dover ──
    "dover": [
        {"category": "subway_station", "name": "Dover MRT", "lat": 1.3040, "lng": 103.7790, "distance_m": 550},
        {"category": "bus_station", "name": "Dover Bus Stop", "lat": 1.3045, "lng": 103.7785, "distance_m": 500},
        {"category": "supermarket", "name": "FairPrice Dover", "lat": 1.3045, "lng": 103.7780, "distance_m": 520},
        {"category": "hawker_centre", "name": "Dover Road Food Centre", "lat": 1.3040, "lng": 103.7775, "distance_m": 600},
        {"category": "pharmacy", "name": "Unity Dover", "lat": 1.3048, "lng": 103.7790, "distance_m": 580},
        {"category": "cafe", "name": "Coffee Bean Dover", "lat": 1.3040, "lng": 103.7795, "distance_m": 480},
    ],
    # ── West Coast ──
    "west_coast": [
        {"category": "bus_station", "name": "West Coast Rd Bus Stop", "lat": 1.3100, "lng": 103.7550, "distance_m": 120},
        {"category": "subway_station", "name": "Clementi MRT", "lat": 1.3150, "lng": 103.7645, "distance_m": 1100},
        {"category": "supermarket", "name": "Giant West Coast", "lat": 1.3105, "lng": 103.7540, "distance_m": 150},
        {"category": "hawker_centre", "name": "West Coast Market Square", "lat": 1.3105, "lng": 103.7560, "distance_m": 100},
        {"category": "restaurant", "name": "West Coast Plaza restaurants", "lat": 1.3120, "lng": 103.7545, "distance_m": 300},
    ],
    # ── Buona Vista ──
    "buona_vista": [
        {"category": "subway_station", "name": "Buona Vista MRT", "lat": 1.3070, "lng": 103.7900, "distance_m": 200},
        {"category": "bus_station", "name": "Buona Vista Bus Terminal", "lat": 1.3075, "lng": 103.7905, "distance_m": 220},
        {"category": "mall", "name": "The Star Vista", "lat": 1.3065, "lng": 103.7890, "distance_m": 180},
        {"category": "supermarket", "name": "Cold Storage The Star Vista", "lat": 1.3065, "lng": 103.7890, "distance_m": 180},
        {"category": "restaurant", "name": "The Star Vista food court", "lat": 1.3068, "lng": 103.7892, "distance_m": 200},
        {"category": "cafe", "name": "Starbucks The Metropolis", "lat": 1.3060, "lng": 103.7905, "distance_m": 250},
        {"category": "gym", "name": "Fitness First Buona Vista", "lat": 1.3065, "lng": 103.7900, "distance_m": 200},
        {"category": "pharmacy", "name": "Watsons The Star Vista", "lat": 1.3065, "lng": 103.7890, "distance_m": 180},
    ],
    # ── Jurong West ──
    "jurong_west": [
        {"category": "subway_station", "name": "Jurong East MRT", "lat": 1.3330, "lng": 103.7430, "distance_m": 600},
        {"category": "bus_station", "name": "Jurong West Bus Interchange", "lat": 1.3400, "lng": 103.7100, "distance_m": 350},
        {"category": "mall", "name": "Jem / Westgate", "lat": 1.3330, "lng": 103.7420, "distance_m": 650},
        {"category": "supermarket", "name": "FairPrice Jurong West", "lat": 1.3405, "lng": 103.7095, "distance_m": 400},
        {"category": "hawker_centre", "name": "Jurong West 505 Market", "lat": 1.3405, "lng": 103.7110, "distance_m": 200},
        {"category": "hospital", "name": "Ng Teng Fong General Hospital", "lat": 1.3340, "lng": 103.7435, "distance_m": 800},
    ],
    # ── Pioneer ──
    "pioneer": [
        {"category": "subway_station", "name": "Pioneer MRT", "lat": 1.3370, "lng": 103.6970, "distance_m": 200},
        {"category": "bus_station", "name": "Pioneer Bus Stop", "lat": 1.3390, "lng": 103.6960, "distance_m": 150},
        {"category": "supermarket", "name": "Giant Pioneer", "lat": 1.3380, "lng": 103.6975, "distance_m": 250},
        {"category": "hawker_centre", "name": "Pioneer Mall Food Court", "lat": 1.3385, "lng": 103.6975, "distance_m": 300},
        {"category": "mall", "name": "Pioneer Mall", "lat": 1.3385, "lng": 103.6975, "distance_m": 300},
    ],
    # ── Boon Lay ──
    "boon_lay": [
        {"category": "subway_station", "name": "Boon Lay MRT", "lat": 1.3350, "lng": 103.7050, "distance_m": 250},
        {"category": "bus_station", "name": "Boon Lay Bus Interchange", "lat": 1.3353, "lng": 103.7053, "distance_m": 280},
        {"category": "mall", "name": "Jurong Point", "lat": 1.3360, "lng": 103.7060, "distance_m": 350},
        {"category": "supermarket", "name": "FairPrice Xtra Jurong Point", "lat": 1.3360, "lng": 103.7060, "distance_m": 350},
        {"category": "hawker_centre", "name": "Boon Lay Place Market", "lat": 1.3355, "lng": 103.7045, "distance_m": 180},
        {"category": "gym", "name": "Anytime Fitness Jurong Point", "lat": 1.3360, "lng": 103.7060, "distance_m": 350},
    ],
    # ── Lakeside ──
    "lakeside": [
        {"category": "subway_station", "name": "Lakeside MRT", "lat": 1.3450, "lng": 103.7200, "distance_m": 500},
        {"category": "bus_station", "name": "Lakeside Bus Stop", "lat": 1.3450, "lng": 103.7190, "distance_m": 480},
        {"category": "supermarket", "name": "FairPrice Lakeside", "lat": 1.3455, "lng": 103.7210, "distance_m": 550},
        {"category": "hawker_centre", "name": "Taman Jurong Market", "lat": 1.3400, "lng": 103.7230, "distance_m": 700},
        {"category": "mall", "name": "Taman Jurong Shopping Centre", "lat": 1.3390, "lng": 103.7235, "distance_m": 800},
    ],
    # ── Bugis ──
    "bugis": [
        {"category": "subway_station", "name": "Bugis MRT", "lat": 1.3000, "lng": 103.8550, "distance_m": 200},
        {"category": "bus_station", "name": "Bugis Bus Stop", "lat": 1.3005, "lng": 103.8555, "distance_m": 180},
        {"category": "mall", "name": "Bugis Junction", "lat": 1.2995, "lng": 103.8555, "distance_m": 150},
        {"category": "mall", "name": "Bugis+", "lat": 1.3005, "lng": 103.8545, "distance_m": 220},
        {"category": "supermarket", "name": "Cold Storage Bugis Junction", "lat": 1.2995, "lng": 103.8555, "distance_m": 150},
        {"category": "hawker_centre", "name": "Albert Centre Market", "lat": 1.3020, "lng": 103.8540, "distance_m": 300},
        {"category": "restaurant", "name": "Arab Street restaurants", "lat": 1.3015, "lng": 103.8580, "distance_m": 400},
        {"category": "cafe", "name": "% Arabica Bugis", "lat": 1.3000, "lng": 103.8560, "distance_m": 250},
        {"category": "hospital", "name": "Raffles Hospital", "lat": 1.3015, "lng": 103.8555, "distance_m": 300},
        {"category": "pharmacy", "name": "Guardian Bugis Junction", "lat": 1.2995, "lng": 103.8555, "distance_m": 150},
        {"category": "gym", "name": "Fitness First Bugis", "lat": 1.3005, "lng": 103.8545, "distance_m": 220},
    ],
    # ── Kallang ──
    "kallang": [
        {"category": "subway_station", "name": "Kallang MRT", "lat": 1.3100, "lng": 103.8700, "distance_m": 550},
        {"category": "bus_station", "name": "Kallang Bus Stop", "lat": 1.3095, "lng": 103.8695, "distance_m": 500},
        {"category": "supermarket", "name": "FairPrice Kallang", "lat": 1.3105, "lng": 103.8710, "distance_m": 600},
        {"category": "hawker_centre", "name": "Geylang Bahru Market", "lat": 1.3130, "lng": 103.8680, "distance_m": 450},
        {"category": "hawker_centre", "name": "Old Airport Road Food Centre", "lat": 1.3080, "lng": 103.8860, "distance_m": 1800},
    ],
    # ── Lavender ──
    "lavender": [
        {"category": "subway_station", "name": "Lavender MRT", "lat": 1.3050, "lng": 103.8600, "distance_m": 250},
        {"category": "bus_station", "name": "Lavender Bus Stop", "lat": 1.3055, "lng": 103.8605, "distance_m": 220},
        {"category": "supermarket", "name": "FairPrice Lavender", "lat": 1.3055, "lng": 103.8595, "distance_m": 280},
        {"category": "hawker_centre", "name": "Lavender Food Square", "lat": 1.3055, "lng": 103.8610, "distance_m": 200},
        {"category": "mall", "name": "City Square Mall", "lat": 1.3110, "lng": 103.8570, "distance_m": 800},
        {"category": "pharmacy", "name": "Guardian Lavender", "lat": 1.3050, "lng": 103.8605, "distance_m": 200},
    ],
    # ── Woodlands ──
    "woodlands": [
        {"category": "subway_station", "name": "Woodlands MRT", "lat": 1.4380, "lng": 103.7890, "distance_m": 1100},
        {"category": "bus_station", "name": "Woodlands Bus Interchange", "lat": 1.4385, "lng": 103.7895, "distance_m": 1150},
        {"category": "mall", "name": "Causeway Point", "lat": 1.4380, "lng": 103.7880, "distance_m": 1050},
        {"category": "supermarket", "name": "FairPrice Woodlands", "lat": 1.4375, "lng": 103.7885, "distance_m": 1000},
        {"category": "hawker_centre", "name": "Woodlands Centre Food Centre", "lat": 1.4430, "lng": 103.7850, "distance_m": 800},
    ],
}

# ═══════════════════════════════════════════════════════════════════
# Institute 配置（12 栋，4 类）
# ═══════════════════════════════════════════════════════════════════

INSTITUTE_CONFIGS: list[dict[str, Any]] = [
    # ═══ Condo 整租型 — 做 studio / 1bed / 2bed ═══
    {
        "name": "Clementi Peak Residences",
        "name_cn": "金文泰峰尚公寓",
        "abbreviation": "CPR",
        "category": "Condo",
        "zone": "central_west",
        "lat": 1.3160, "lng": 103.7655,
        "address": "12 Clementi Ave 1, Singapore 129957",
        "street": "Clementi Ave 1",
        "district": "Clementi",
        "city": "Singapore",
        "country": "SG",
        "npc": "CL-NPC",
        "postal_code": "129957",
        "building_type": "condominium",
        "total_floors": 25, "total_units": 200, "year_built": 2018,
        "has_elevator": True,
        "description": "位于金文泰核心地段的高端公寓，步行 3 分钟到 Clementi MRT 和 Clementi Mall。NUS 学生首选，楼下有泳池、健身房、BBQ 区，24 小时安保。",
        "building_amenities": ["健身房", "泳池", "自习室", "24小时安保", "电梯", "停车位", "BBQ区", "门禁系统", "快递代收"],
        "poi_zone": "clementi",
        "mrt_proximity": "near",
        "target_uni": "NUS", "uni_id": 1,
        "uni_proximity": "near",
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
        "name": "Buona Vista Suites",
        "name_cn": "波那维斯达公馆",
        "abbreviation": "BVS",
        "category": "Condo",
        "zone": "central_west",
        "lat": 1.3075, "lng": 103.7910,
        "address": "8 Biopolis Dr, Singapore 138622",
        "street": "Biopolis Dr",
        "district": "Buona Vista",
        "city": "Singapore",
        "country": "SG",
        "npc": "BV-NPC",
        "postal_code": "138622",
        "building_type": "condominium",
        "total_floors": 18, "total_units": 150, "year_built": 2020,
        "has_elevator": True,
        "description": "Biopolis 科技园旁高端公寓，步行 2 分钟到 Buona Vista MRT 和 The Star Vista，NUS 和科技园区白领的首选。Metropolis 写字楼群、Fusionopolis 近在咫尺。",
        "building_amenities": ["健身房", "泳池", "自习室", "24小时安保", "电梯", "停车位", "网球场", "门禁系统", "快递代收"],
        "poi_zone": "buona_vista",
        "mrt_proximity": "near",
        "target_uni": "NUS", "uni_id": 1,
        "uni_proximity": "near",
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
        "name": "Boon Lay Gardens",
        "name_cn": "文礼花园公寓",
        "abbreviation": "BLG",
        "category": "Condo",
        "zone": "west",
        "lat": 1.3355, "lng": 103.7055,
        "address": "21 Boon Lay Dr, Singapore 649877",
        "street": "Boon Lay Dr",
        "district": "Boon Lay",
        "city": "Singapore",
        "country": "SG",
        "npc": "BL-NPC",
        "postal_code": "649877",
        "building_type": "condominium",
        "total_floors": 15, "total_units": 120, "year_built": 2017,
        "has_elevator": True,
        "description": "文礼地铁站旁中端公寓，紧邻 Jurong Point 购物中心。NTU 学生性价比之选，公寓设施齐全。",
        "building_amenities": ["健身房", "泳池", "洗衣房", "24小时安保", "电梯", "停车位", "门禁系统"],
        "poi_zone": "boon_lay",
        "mrt_proximity": "near",
        "target_uni": "NTU", "uni_id": 2,
        "uni_proximity": "mid",
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
        "name": "Lakeside Tower Condominium",
        "name_cn": "湖畔尚苑公寓",
        "abbreviation": "LST",
        "category": "Condo",
        "zone": "west",
        "lat": 1.3458, "lng": 103.7210,
        "address": "38 Yuan Ching Rd, Singapore 618653",
        "street": "Yuan Ching Rd",
        "district": "Lakeside",
        "city": "Singapore",
        "country": "SG",
        "npc": "LS-NPC",
        "postal_code": "618653",
        "building_type": "condominium",
        "total_floors": 12, "total_units": 90, "year_built": 2015,
        "has_elevator": True,
        "description": "裕廊湖畔宁静公寓，步行 5 分钟到 Lakeside MRT 和裕廊湖花园。环境优美，适合静心学习，NTU 学生偏爱之选。",
        "building_amenities": ["泳池", "自习室", "洗衣房", "24小时安保", "电梯", "停车位", "门禁系统", "BBQ区"],
        "poi_zone": "lakeside",
        "mrt_proximity": "mid",
        "target_uni": "NTU", "uni_id": 2,
        "uni_proximity": "mid",
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

    # ═══ HDB 单间型 — 做 common room / master room ═══
    {
        "name": "Dover Park HDB",
        "name_cn": "杜佛园组屋",
        "abbreviation": "DPH",
        "category": "HDB",
        "zone": "central_west",
        "lat": 1.3048, "lng": 103.7790,
        "address": "Blk 28 Dover Crescent, Singapore 130028",
        "street": "Dover Crescent",
        "district": "Dover",
        "city": "Singapore",
        "country": "SG",
        "npc": "DV-NPC",
        "postal_code": "130028",
        "building_type": "HDB",
        "total_floors": 12, "total_units": 96, "year_built": 2005,
        "has_elevator": True,
        "description": "Dover Crescent 组屋，步行 6 分钟到 Dover MRT，距离 NUS 仅一站公交。周边有食阁、超市，生活便利。",
        "building_amenities": ["电梯", "洗衣房", "门禁系统"],
        "poi_zone": "dover",
        "mrt_proximity": "mid",
        "target_uni": "NUS", "uni_id": 1,
        "uni_proximity": "mid",
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
        "name": "West Coast Lodge HDB",
        "name_cn": "西海岸花园组屋",
        "abbreviation": "WCL",
        "category": "HDB",
        "zone": "central_west",
        "lat": 1.3105, "lng": 103.7545,
        "address": "Blk 712 Clementi West St 2, Singapore 120712",
        "street": "Clementi West St 2",
        "district": "West Coast",
        "city": "Singapore",
        "country": "SG",
        "npc": "WC-NPC",
        "postal_code": "120712",
        "building_type": "HDB",
        "total_floors": 10, "total_units": 80, "year_built": 1998,
        "has_elevator": True,
        "description": "西海岸组屋，距离 NUS 仅 2 公里，门前有公交直达。周边食阁、超市齐全，价格亲民，预算有限的 NUS 学生首选。",
        "building_amenities": ["电梯", "洗衣房"],
        "poi_zone": "west_coast",
        "mrt_proximity": "far",
        "target_uni": "NUS", "uni_id": 1,
        "uni_proximity": "mid",
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
        "name": "Jurong West Central HDB",
        "name_cn": "裕廊西中心组屋",
        "abbreviation": "JWC",
        "category": "HDB",
        "zone": "west",
        "lat": 1.3410, "lng": 103.7095,
        "address": "Blk 654 Jurong West St 61, Singapore 640654",
        "street": "Jurong West St 61",
        "district": "Jurong West",
        "city": "Singapore",
        "country": "SG",
        "npc": "JW-NPC",
        "postal_code": "640654",
        "building_type": "HDB",
        "total_floors": 16, "total_units": 128, "year_built": 2008,
        "has_elevator": True,
        "description": "裕廊西成熟社区，步行 6 分钟到 Jurong West 食阁和超市。公交直达 NTU 校园，周边社区设施完善。",
        "building_amenities": ["电梯", "停车位"],
        "poi_zone": "jurong_west",
        "mrt_proximity": "mid",
        "target_uni": "NTU", "uni_id": 2,
        "uni_proximity": "mid",
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
    {
        "name": "Kallang River HDB",
        "name_cn": "加冷河畔组屋",
        "abbreviation": "KRH",
        "category": "HDB",
        "zone": "city_fringe",
        "lat": 1.3105, "lng": 103.8705,
        "address": "Blk 117 Jalan Besar, Singapore 208835",
        "street": "Jalan Besar",
        "district": "Kallang",
        "city": "Singapore",
        "country": "SG",
        "npc": "KL-NPC",
        "postal_code": "208835",
        "building_type": "HDB",
        "total_floors": 14, "total_units": 112, "year_built": 2010,
        "has_elevator": True,
        "description": "加冷河畔组屋，步行 6 分钟到 Kallang MRT，2 站到 Bugis/SMU。周边有著名的旧机场路熟食中心，吃货天堂。",
        "building_amenities": ["电梯", "停车位", "洗衣房", "快递代收"],
        "poi_zone": "kallang",
        "mrt_proximity": "mid",
        "target_uni": "SMU", "uni_id": 3,
        "uni_proximity": "mid",
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
        "name": "Lavender Court HDB",
        "name_cn": "劳明达苑组屋",
        "abbreviation": "LVC",
        "category": "HDB",
        "zone": "city_fringe",
        "lat": 1.3058, "lng": 103.8605,
        "address": "Blk 808 French Rd, Singapore 200808",
        "street": "French Rd",
        "district": "Lavender",
        "city": "Singapore",
        "country": "SG",
        "npc": "LV-NPC",
        "postal_code": "200808",
        "building_type": "HDB",
        "total_floors": 20, "total_units": 160, "year_built": 2012,
        "has_elevator": True,
        "description": "劳明达核心地段组屋，步行 3 分钟到 Lavender MRT。靠近 City Square Mall 和 Mustafa Centre，SMU 学生的高性价比选择。",
        "building_amenities": ["电梯", "停车位", "洗衣房", "门禁系统"],
        "poi_zone": "lavender",
        "mrt_proximity": "near",
        "target_uni": "SMU", "uni_id": 3,
        "uni_proximity": "mid",
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

    # ═══ Ensuite 学生公寓型 — 做 ensuite（单/双） ═══
    {
        "name": "Pioneer Student Residence",
        "name_cn": "先驱学生公寓",
        "abbreviation": "PSR",
        "category": "HDB",  # 学生公寓本质是改造后的 HDB/宿舍，按 HDB 定价
        "zone": "west",
        "lat": 1.3385, "lng": 103.6965,
        "address": "55 Pioneer Sector, Singapore 628400",
        "street": "Pioneer Sector",
        "district": "Pioneer",
        "city": "Singapore",
        "country": "SG",
        "npc": "PN-NPC",
        "postal_code": "628400",
        "building_type": "student_hostel",
        "total_floors": 8, "total_units": 120, "year_built": 2014,
        "has_elevator": True,
        "description": "NTU 校门口学生公寓，步行 10 分钟到 NTU 主校区。Pioneer MRT 步行 2 分钟，楼下有免费校车接驳。以 ensuite 单人间为主，配套齐全。",
        "building_amenities": ["自习室", "洗衣房", "24小时安保", "电梯", "校车接驳", "门禁系统", "快递代收"],
        "poi_zone": "pioneer",
        "mrt_proximity": "near",
        "target_uni": "NTU", "uni_id": 2,
        "uni_proximity": "near",
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

    # ═══ Shared 经济型 — 做 shared / common ═══
    {
        "name": "Woodlands Budget Hostel",
        "name_cn": "兀兰经济公寓",
        "abbreviation": "WBH",
        "category": "HDB",
        "zone": "suburb",
        "lat": 1.4420, "lng": 103.7860,
        "address": "Blk 888 Woodlands Dr 50, Singapore 730888",
        "street": "Woodlands Dr 50",
        "district": "Woodlands",
        "city": "Singapore",
        "country": "SG",
        "npc": "WD-NPC",
        "postal_code": "730888",
        "building_type": "HDB",
        "total_floors": 11, "total_units": 88, "year_built": 2000,
        "has_elevator": True,
        "description": "兀兰经济型住宿，距离市区较远但价格极低。适合预算紧张的学生或短期实习，可搭 North-South Line 到市区约 35 分钟。",
        "building_amenities": ["电梯", "洗衣房", "快递代收"],
        "poi_zone": "woodlands",
        "mrt_proximity": "far",
        "target_uni": "NTU", "uni_id": 2,
        "uni_proximity": "far",
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

    # ═══ City Condo — Bugis 核心区 ═══
    {
        "name": "Bugis Central Suites",
        "name_cn": "武吉士中央公馆",
        "abbreviation": "BCS",
        "category": "Condo",
        "zone": "city",
        "lat": 1.2998, "lng": 103.8558,
        "address": "33 Victoria St, Singapore 188020",
        "street": "Victoria St",
        "district": "Bugis",
        "city": "Singapore",
        "country": "SG",
        "npc": "BG-NPC",
        "postal_code": "188020",
        "building_type": "condominium",
        "total_floors": 30, "total_units": 240, "year_built": 2021,
        "has_elevator": True,
        "description": "武吉士核心区高端公寓，步行 2 分钟到 Bugis MRT 和 Bugis Junction。SMU 学生步行 5 分钟到校，市中心生活配套无与伦比。",
        "building_amenities": ["健身房", "泳池", "自习室", "洗衣房", "24小时安保", "电梯", "停车位", "网球场", "BBQ区", "门禁系统", "快递代收"],
        "poi_zone": "bugis",
        "mrt_proximity": "near",
        "target_uni": "SMU", "uni_id": 3,
        "uni_proximity": "near",
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
]

# ═══════════════════════════════════════════════════════════════════
# 数据库操作
# ═══════════════════════════════════════════════════════════════════

ROOM_TYPE_LABELS: dict[str, str] = {
    "studio": "单人Studio",
    "1bed": "一室一厅",
    "2bed": "两室一厅",
    "3bed": "三室两卫",
    "ensuite": "独卫套间",
    "master": "主卧套间",
    "common": "普通单间",
    "shared": "合租床位",
}

ROOM_TYPE_TO_PROPERTY_TYPE: dict[str, str] = {
    "studio": "studio", "1bed": "1bed", "2bed": "2bed", "3bed": "3bed",
    "ensuite": "ensuite", "master": "ensuite", "common": "shared", "shared": "shared",
}


async def _get_or_create_admin(session) -> int:
    """获取或创建管理员用户，返回 user_id。"""
    result = await session.execute(
        select(User).where(User.username == "admin").limit(1)
    )
    admin = result.scalar_one_or_none()
    if admin:
        return admin.id

    admin = User(
        username="admin",
        email="admin@rental-housing.local",
        password_hash="$2b$12$placeholder",  # 不可登录，仅满足 NOT NULL 约束
        role=UserRole.admin,
        status=UserStatus.active,
    )
    session.add(admin)
    await session.flush()
    return admin.id


def _make_unit_type_name(cfg: dict) -> str:
    """生成 UnitType 名称。"""
    if "label_override" in cfg:
        return cfg["label_override"]
    base = ROOM_TYPE_LABELS.get(cfg["type"], cfg["type"])
    tier = "高级" if cfg["tier"] == "premium" else "标准"
    return f"{base}（{tier}）"


async def seed(clear_existing: bool = False) -> None:
    """主流程。"""
    async with async_session_maker() as session:
        # ── 清理 ──
        if clear_existing:
            print("⚠ 清理现有新加坡测试数据...")
            # 先删依赖表（外键约束）
            await session.execute(delete(InstituteCommute))
            await session.execute(delete(InstitutePOI))
            # 删 UnitType（FK → Institute）
            await session.execute(
                delete(UnitType).where(
                    UnitType.institute_id.in_(
                        select(Institute.id).where(Institute.country == "SG")
                    )
                )
            )
            await session.execute(
                delete(Institute).where(Institute.country == "SG")
            )
            await session.commit()
            print("✓ 已清理\n")

        admin_id = await _get_or_create_admin(session)

        # ── 遍历 Institute 配置 ──
        total_ut = 0
        summary_rows: list[dict] = []

        for cfg in INSTITUTE_CONFIGS:
            # 插入 Institute
            inst = Institute(
                name=cfg["name"],
                name_cn=cfg["name_cn"],
                abbreviation=cfg["abbreviation"],
                address=cfg["address"],
                street=cfg["street"],
                district=cfg["district"],
                city=cfg["city"],
                country=cfg["country"],
                npc=cfg.get("npc"),
                postal_code=cfg.get("postal_code"),
                latitude=Decimal(str(cfg["lat"])),
                longitude=Decimal(str(cfg["lng"])),
                building_type=cfg.get("building_type"),
                total_floors=cfg.get("total_floors"),
                total_units=cfg.get("total_units"),
                year_built=cfg.get("year_built"),
                has_elevator=cfg.get("has_elevator", False),
                amenities=cfg.get("building_amenities", []),
                description=cfg.get("description"),
                status=InstituteStatus.active,
                created_by=admin_id,
            )
            session.add(inst)
            await session.flush()  # 获取 inst.id

            # ── 插入 UnitTypes ──
            unit_prices: list[Decimal] = []
            for ut_cfg in cfg["unit_types"]:
                price, breakdown = compute_price(
                    room_type=ut_cfg["type"],
                    zone=cfg["zone"],
                    mrt_proximity=cfg["mrt_proximity"],
                    uni_proximity=cfg["uni_proximity"],
                    room_amenities=ut_cfg["amenities"],
                )

                unit_prices.append(price)

                ut = UnitType(
                    institute_id=inst.id,
                    name=_make_unit_type_name(ut_cfg),
                    property_type=ROOM_TYPE_TO_PROPERTY_TYPE.get(ut_cfg["type"], "shared"),
                    bedrooms=_guess_bedrooms(ut_cfg["type"]),
                    bathrooms=2 if ut_cfg["type"] in ("2bed", "3bed") else 1,
                    hall_count=0,
                    area_sqm=ut_cfg.get("area_sqm"),
                    base_rent=price,
                    deposit_type=DepositType.one_month,
                    deposit_amount=int(price),
                    currency="SGD",
                    amenities=ut_cfg["amenities"],
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

            # 卡片最低价
            card_price = min(unit_prices)

            summary_rows.append({
                "name": cfg["name_cn"],
                "cat": cfg["category"],
                "zone": cfg["zone"],
                "mrt": cfg["mrt_proximity"],
                "uni": cfg["uni_proximity"],
                "uts": len(cfg["unit_types"]),
                "card": card_price,
                "range": f"S${min(unit_prices)} - S${max(unit_prices)}",
            })

            # ── POI 数据 ──
            poi_items = POI_TEMPLATES.get(cfg["poi_zone"], [])
            map_poi_data: dict[str, list] = {}
            for item in poi_items:
                cat = item["category"]
                if cat not in map_poi_data:
                    map_poi_data[cat] = []
                map_poi_data[cat].append({
                    "name": item["name"],
                    "lat": item["lat"],
                    "lng": item["lng"],
                    "distance_m": item["distance_m"],
                })

            poi = InstitutePOI(
                institute_id=inst.id,
                content=f"{cfg['name']} 周边设施描述",
                poi_data={"categories": list(map_poi_data.keys()), "total_pois": len(poi_items)},
                map_poi_data=map_poi_data,
                safety_data={"crime_rate": "low" if cfg["zone"] != "suburb" else "very_low"},
                generated_at=datetime.now(timezone.utc),
            )
            session.add(poi)

            # ── Commute 数据 ──
            commute = InstituteCommute(
                institute_id=inst.id,
                university_id=cfg["uni_id"],
                transit_min=cfg["commute"]["transit_min"],
                walk_min=cfg["commute"]["walk_min"],
                drive_min=cfg["commute"]["drive_min"],
                source="seed_script",
                computed_at=datetime.now(timezone.utc),
            )
            session.add(commute)

        await session.commit()

        # ── 打印汇总 ──
        print("\n" + "=" * 120)
        print(f"{'Institute':<22} {'类型':<8} {'区域':<14} {'MRT':<6} {'大学':<6} {'户型数':<6} {'卡片价':<10} {'价格区间'}")
        print("=" * 120)
        for r in summary_rows:
            print(f"{r['name']:<22} {r['cat']:<8} {r['zone']:<14} {r['mrt']:<6} {r['uni']:<6} {r['uts']:<6} S${r['card']:<9} {r['range']}")
        print("=" * 120)
        print(f"\n总计: {len(summary_rows)} 个 Institute, {total_ut} 个 UnitType\n")


def _guess_bedrooms(rt: str) -> int:
    if rt == "2bed": return 2
    if rt == "3bed": return 3
    return 1


def _guess_total_count(rt: str, cat: str) -> int:
    """合理估算可租房源数量。"""
    if rt == "shared": return random.randint(4, 8)
    if rt == "common": return random.randint(3, 6)
    if rt == "master": return random.randint(2, 4)
    if rt == "ensuite": return random.randint(3, 10)
    return random.randint(1, 4)  # studio / 1bed / 2bed


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
        print("🏠 测试：打印前 3 个 Institute 的定价明细")
        print("=" * 60)
        for cfg in INSTITUTE_CONFIGS[:3]:
            print(f"\n【{cfg['name_cn']}】{cfg['category']} | {cfg['zone']} | MRT={cfg['mrt_proximity']} | Uni={cfg['uni_proximity']}")
            for ut_cfg in cfg["unit_types"]:
                price, bd = compute_price(
                    room_type=ut_cfg["type"],
                    zone=cfg["zone"],
                    mrt_proximity=cfg["mrt_proximity"],
                    uni_proximity=cfg["uni_proximity"],
                    room_amenities=ut_cfg["amenities"],
                )
                print(f"  {_make_unit_type_name(ut_cfg):<20} S${price:<8} | 基准=S${bd.get('基准价',0)} "
                      f"区位={bd.get('区位调整',0):+.2f} 配套+S${bd.get('配套加价',0)} 抖动={bd.get('抖动',1)}")
        print("\n✅ --dry-run 完成（未写库）\n")
        return

    await seed(clear_existing=clear)
    print("✅ 种子数据写入完成\n")


if __name__ == "__main__":
    asyncio.run(main())

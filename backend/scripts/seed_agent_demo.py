"""Agent 演示数据脚本：幂等创建房源，并补齐模拟 POI、通勤与 embedding。"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models.institute import Institute, InstituteStatus
from app.models.poi import PropertyPOI
from app.models.property import Property
from app.models.room_commute import RoomCommute
from app.models.unit_type import DepositType, UnitType, UnitTypeStatus
from app.models.university import University
from app.models.user import User, UserRole, UserStatus


DEMO_USERNAME = "agent_demo_landlord"
DEMO_EMAIL = "agent-demo-landlord@example.com"
DEMO_PASSWORD = "agent-demo-2026"

UNIVERSITIES = [
    {
        "name": "National University of Singapore",
        "name_cn": "新加坡国立大学",
        "abbreviation": "NUS",
        "aliases": ["nus", "新加坡国立大学", "新国大"],
        "city": "新加坡",
        "country": "SG",
        "latitude": Decimal("1.296600"),
        "longitude": Decimal("103.776400"),
    },
    {
        "name": "University College London",
        "name_cn": "伦敦大学学院",
        "abbreviation": "UCL",
        "aliases": ["ucl", "伦敦大学学院"],
        "city": "伦敦",
        "country": "GB",
        "latitude": Decimal("51.524600"),
        "longitude": Decimal("-0.134000"),
    },
    {
        "name": "University of California, Los Angeles",
        "name_cn": "加州大学洛杉矶分校",
        "abbreviation": "UCLA",
        "aliases": ["ucla", "加州大学洛杉矶分校"],
        "city": "洛杉矶",
        "country": "US",
        "latitude": Decimal("34.068900"),
        "longitude": Decimal("-118.445200"),
    },
    {
        "name": "The University of Hong Kong",
        "name_cn": "香港大学",
        "abbreviation": "HKU",
        "aliases": ["hku", "香港大学", "港大"],
        "city": "香港",
        "country": "HK",
        "latitude": Decimal("22.283000"),
        "longitude": Decimal("114.137100"),
    },
]

MARKETS = [
    {
        "business_id": "DEMO-SG-NUS",
        "name": "NUS West Coast Student Residence",
        "name_cn": "新加坡国立大学西海岸学生公寓",
        "address": "88 West Coast Road, Singapore 126790",
        "district": "金文泰",
        "city": "新加坡",
        "country": "SG",
        "latitude": "1.305400",
        "longitude": "103.766800",
        "amenities": ["WiFi", "健身房", "自习室", "24小时安保", "洗衣房", "近公交"],
        "description": "靠近 NUS 的学生公寓，适合需要稳定通勤和完整生活配套的学生。",
        "currency": "SGD",
        "units": [
            ("Studio 单人套间", 0, 1, "1850", "24", ["独立卫浴", "独立厨房", "家具齐全"]),
            ("Ensuite 独卫套间", 1, 1, "1550", "20", ["独立卫浴", "共享厨房", "家具齐全"]),
            ("两室一厅", 2, 1, "3200", "62", ["独立厨房", "阳台", "洗衣机"]),
        ],
    },
    {
        "business_id": "DEMO-SG-DOVER",
        "name": "Dover Campus Garden Lodge",
        "name_cn": "杜佛校园花园公寓",
        "address": "12 Dover Close East, Singapore 139658",
        "district": "杜佛",
        "city": "新加坡",
        "country": "SG",
        "latitude": "1.304800",
        "longitude": "103.781600",
        "amenities": ["WiFi", "花园", "自习室", "24小时安保", "洗衣房", "近地铁"],
        "description": "位于杜佛生活区的学生公寓，兼顾 NUS 通勤、安静环境与日常采购。",
        "currency": "SGD",
        "units": [
            ("Garden Studio", 0, 1, "1980", "26", ["独立卫浴", "独立厨房", "花园景"]),
            ("Compact Ensuite", 1, 1, "1480", "18", ["独立卫浴", "共享厨房", "书桌"]),
            ("One Bedroom Corner", 1, 1, "2550", "41", ["独立厨房", "转角采光", "洗衣机"]),
            ("Two Bedroom Loft", 2, 2, "3450", "68", ["双卫", "挑高客厅", "阳台"]),
        ],
    },
    {
        "business_id": "DEMO-SG-QUEENSTOWN",
        "name": "Queenstown Scholar Suites",
        "name_cn": "女皇镇学者公寓",
        "address": "61 Commonwealth Drive, Singapore 140061",
        "district": "女皇镇",
        "city": "新加坡",
        "country": "SG",
        "latitude": "1.300900",
        "longitude": "103.797400",
        "amenities": ["WiFi", "健身房", "共享厨房", "自习室", "门禁", "近超市"],
        "description": "女皇镇成熟社区内的学生公寓，适合希望兼顾学习空间和生活便利的租客。",
        "currency": "SGD",
        "units": [
            ("Skyline Studio", 0, 1, "2050", "25", ["独立卫浴", "开放厨房", "高楼层"]),
            ("Deluxe Ensuite", 1, 1, "1580", "21", ["独立卫浴", "共享厨房", "大书桌"]),
            ("One Bedroom Balcony", 1, 1, "2680", "45", ["独立厨房", "阳台", "洗衣机"]),
            ("Two Bedroom City View", 2, 2, "3680", "72", ["双卫", "城市景观", "独立厨房"]),
        ],
    },
    {
        "business_id": "DEMO-GB-UCL",
        "name": "Bloomsbury UCL Residence",
        "name_cn": "伦敦大学学院布鲁姆斯伯里公寓",
        "address": "18 Gower Street, London WC1E 6BT",
        "district": "布鲁姆斯伯里",
        "city": "伦敦",
        "country": "GB",
        "latitude": "51.522900",
        "longitude": "-0.132100",
        "amenities": ["WiFi", "门禁", "自习室", "洗衣房", "近地铁", "账单全包"],
        "description": "步行可达 UCL 的市中心学生公寓，周边交通、超市和餐饮便利。",
        "currency": "GBP",
        "units": [
            ("Classic Studio", 0, 1, "1850", "21", ["独立卫浴", "独立厨房", "家具齐全"]),
            ("Premium Ensuite", 1, 1, "1450", "18", ["独立卫浴", "共享厨房", "书桌"]),
            ("Shared Twin Room", 1, 1, "980", "16", ["合租", "共享厨房", "账单全包"]),
        ],
    },
    {
        "business_id": "DEMO-US-UCLA",
        "name": "Westwood UCLA Apartments",
        "name_cn": "洛杉矶西木区 UCLA 公寓",
        "address": "950 Gayley Avenue, Los Angeles, CA 90024",
        "district": "Westwood",
        "city": "洛杉矶",
        "country": "US",
        "latitude": "34.063800",
        "longitude": "-118.447000",
        "amenities": ["WiFi", "健身房", "门禁", "停车位", "洗衣房", "近校园"],
        "description": "位于 Westwood 核心区，步行可达 UCLA，适合本科生、研究生和访问学者。",
        "currency": "USD",
        "units": [
            ("Furnished Studio", 0, 1, "2350", "32", ["独立卫浴", "独立厨房", "家具齐全"]),
            ("One Bedroom", 1, 1, "2850", "48", ["独立厨房", "空调", "洗衣机"]),
            ("Two Bedroom Shared", 2, 2, "4100", "76", ["合租", "双卫", "阳台"]),
        ],
    },
    {
        "business_id": "DEMO-HK-HKU",
        "name": "Kennedy Town HKU Residence",
        "name_cn": "香港大学坚尼地城学生公寓",
        "address": "38 Belcher's Street, Kennedy Town, Hong Kong",
        "district": "坚尼地城",
        "city": "香港",
        "country": "HK",
        "latitude": "22.283900",
        "longitude": "114.128700",
        "amenities": ["WiFi", "门禁", "电梯", "洗衣房", "近地铁", "海景"],
        "description": "靠近港大和坚尼地城地铁站，适合重视通勤与生活便利的学生。",
        "currency": "HKD",
        "units": [
            ("海景 Studio", 0, 1, "16800", "22", ["独立卫浴", "开放厨房", "家具齐全"]),
            ("独卫单间", 1, 1, "12500", "16", ["独立卫浴", "共享厨房", "书桌"]),
            ("两房合租", 2, 1, "23800", "43", ["合租", "独立厨房", "海景"]),
        ],
    },
]

# 追加更多常用留学市场，整批数据共 11 个公寓、40 个户型、80 间房。
MARKETS.extend([
    {
        "business_id": "DEMO-SG-ONE-NORTH",
        "name": "One-North Campus Commons",
        "name_cn": "纬壹校园共享公寓",
        "address": "8 Ayer Rajah Crescent, Singapore 139939",
        "district": "纬壹",
        "city": "新加坡",
        "country": "SG",
        "latitude": "1.299900",
        "longitude": "103.787100",
        "amenities": ["WiFi", "健身房", "自习室", "共享厨房", "门禁", "近地铁"],
        "description": "位于纬壹科技园生活圈，适合希望兼顾 NUS 通勤、学习与实习的学生。",
        "currency": "SGD",
        "units": [
            ("Urban Studio", 0, 1, "2080", "27", ["独立卫浴", "开放厨房", "家具齐全"]),
            ("Study Ensuite", 1, 1, "1620", "21", ["独立卫浴", "共享厨房", "大书桌"]),
            ("One Bedroom Flex", 1, 1, "2720", "44", ["独立厨房", "洗衣机", "储物间"]),
            ("Two Bedroom Share", 2, 2, "3520", "69", ["合租", "双卫", "阳台"]),
        ],
    },
    {
        "business_id": "DEMO-SG-BUKIT-TIMAH",
        "name": "Bukit Timah Study House",
        "name_cn": "武吉知马学习公寓",
        "address": "116 Clementi Road, Singapore 129791",
        "district": "武吉知马",
        "city": "新加坡",
        "country": "SG",
        "latitude": "1.323200",
        "longitude": "103.769100",
        "amenities": ["WiFi", "花园", "阅读室", "洗衣房", "停车位", "近公交"],
        "description": "安静的低密度学生公寓，适合偏好绿化、阅读空间和稳定公交通勤的租客。",
        "currency": "SGD",
        "units": [
            ("Garden Studio", 0, 1, "1940", "25", ["独立卫浴", "小厨房", "花园景"]),
            ("Quiet Ensuite", 1, 1, "1510", "19", ["独立卫浴", "共享厨房", "书桌"]),
            ("One Bedroom Garden", 1, 1, "2480", "42", ["独立厨房", "露台", "洗衣机"]),
            ("Two Bedroom Courtyard", 2, 1, "3280", "65", ["合租", "独立厨房", "庭院"]),
        ],
    },
    {
        "business_id": "DEMO-GB-CAMDEN",
        "name": "Camden Academic Court",
        "name_cn": "伦敦卡姆登学术公寓",
        "address": "42 Camden Road, London NW1 9DR",
        "district": "卡姆登",
        "city": "伦敦",
        "country": "GB",
        "latitude": "51.539600",
        "longitude": "-0.142600",
        "amenities": ["WiFi", "门禁", "自习室", "洗衣房", "自行车库", "账单全包"],
        "description": "卡姆登生活区内的学生公寓，可乘地铁或公交前往 UCL，餐饮采购选择丰富。",
        "currency": "GBP",
        "units": [
            ("Compact Studio", 0, 1, "1720", "20", ["独立卫浴", "独立厨房", "账单全包"]),
            ("Classic Ensuite", 1, 1, "1320", "17", ["独立卫浴", "共享厨房", "书桌"]),
            ("Large Ensuite", 1, 1, "1540", "22", ["独立卫浴", "共享厨房", "大窗"]),
            ("Twin Shared Flat", 2, 1, "2280", "46", ["合租", "独立厨房", "客厅"]),
        ],
    },
    {
        "business_id": "DEMO-US-SAWTELLE",
        "name": "Sawtelle Bruin Living",
        "name_cn": "洛杉矶索特尔学生公寓",
        "address": "2025 Sawtelle Boulevard, Los Angeles, CA 90025",
        "district": "Sawtelle",
        "city": "洛杉矶",
        "country": "US",
        "latitude": "34.040400",
        "longitude": "-118.443700",
        "amenities": ["WiFi", "健身房", "门禁", "停车位", "洗衣房", "近公交"],
        "description": "位于 Sawtelle 餐饮生活区，可乘公交前往 UCLA，适合重视生活便利的学生。",
        "currency": "USD",
        "units": [
            ("Micro Studio", 0, 1, "2180", "28", ["独立卫浴", "独立厨房", "空调"]),
            ("Furnished One Bedroom", 1, 1, "2680", "45", ["独立厨房", "家具齐全", "洗衣机"]),
            ("One Bedroom Plus", 1, 1, "2920", "52", ["独立厨房", "书房角", "阳台"]),
            ("Two Bedroom Shared", 2, 2, "3980", "74", ["合租", "双卫", "停车位"]),
        ],
    },
    {
        "business_id": "DEMO-HK-SAI-YING-PUN",
        "name": "Sai Ying Pun Campus Homes",
        "name_cn": "香港西营盘校园公寓",
        "address": "128 Des Voeux Road West, Sai Ying Pun, Hong Kong",
        "district": "西营盘",
        "city": "香港",
        "country": "HK",
        "latitude": "22.286400",
        "longitude": "114.143600",
        "amenities": ["WiFi", "门禁", "电梯", "自习区", "洗衣房", "近地铁"],
        "description": "西营盘地铁站生活圈内的学生公寓，前往港大方便，餐饮和日常采购密集。",
        "currency": "HKD",
        "units": [
            ("城市景 Studio", 0, 1, "15800", "20", ["独立卫浴", "开放厨房", "家具齐全"]),
            ("标准独卫单间", 1, 1, "11800", "15", ["独立卫浴", "共享厨房", "书桌"]),
            ("宽敞独卫单间", 1, 1, "13600", "19", ["独立卫浴", "共享厨房", "大窗"]),
            ("两房合租套间", 2, 1, "22600", "41", ["合租", "独立厨房", "客厅"]),
        ],
    },
])


COMMUTE_BASES: dict[str, tuple[int, int, int]] = {
    "DEMO-SG-NUS": (22, 58, 13),
    "DEMO-SG-DOVER": (18, 48, 12),
    "DEMO-SG-QUEENSTOWN": (28, 78, 18),
    "DEMO-SG-ONE-NORTH": (21, 62, 14),
    "DEMO-SG-BUKIT-TIMAH": (25, 72, 16),
    "DEMO-GB-UCL": (8, 16, 7),
    "DEMO-GB-CAMDEN": (19, 38, 14),
    "DEMO-US-UCLA": (10, 18, 6),
    "DEMO-US-SAWTELLE": (24, 66, 15),
    "DEMO-HK-HKU": (12, 24, 8),
    "DEMO-HK-SAI-YING-PUN": (9, 19, 7),
}


def validate_demo_catalog() -> None:
    """启动写库前校验演示房源名称，避免卡片和对比列表出现重名。"""
    business_ids: set[str] = set()
    market_names: set[str] = set()
    property_titles: set[str] = set()
    for market in MARKETS:
        business_id = str(market["business_id"])
        market_name = str(market["name_cn"]).strip()
        if business_id in business_ids:
            raise ValueError(f"演示公寓 business_id 重复：{business_id}")
        if market_name in market_names:
            raise ValueError(f"演示公寓名称重复：{market_name}")
        business_ids.add(business_id)
        market_names.add(market_name)

        unit_names: set[str] = set()
        for unit_data in market["units"]:
            unit_name = str(unit_data[0]).strip()
            if unit_name in unit_names:
                raise ValueError(f"{market_name} 的房型名称重复：{unit_name}")
            unit_names.add(unit_name)
            for room_index in range(1, 3):
                title = f"{market_name} · {unit_name} {room_index}"
                if title in property_titles:
                    raise ValueError(f"演示房源名称重复：{title}")
                property_titles.add(title)


def _simulated_poi_payload(room: Property, market: dict[str, Any]) -> tuple[str, dict, dict]:
    """按房源 ID 稳定生成一组可复现的周边设施数据。"""
    seed = int(room.id or 0)
    district = str(market["district"])
    lat = float(market["latitude"])
    lng = float(market["longitude"])
    distances = {
        "transit": 180 + seed % 7 * 45,
        "bus": 90 + seed % 5 * 35,
        "supermarket": 140 + seed % 6 * 55,
        "hospital": 520 + seed % 8 * 95,
        "gym": 260 + seed % 7 * 70,
        "dining": 110 + seed % 6 * 40,
    }
    poi_data = {
        "交通": [
            {"name": f"{district}地铁站", "distance": f"{distances['transit']}m", "keyword": "地铁站"},
            {"name": f"{district}社区巴士站", "distance": f"{distances['bus']}m", "keyword": "公交站"},
        ],
        "购物": [
            {"name": f"{district}生活超市", "distance": f"{distances['supermarket']}m", "keyword": "超市"},
            {"name": f"{district}便利店", "distance": f"{distances['supermarket'] + 85}m", "keyword": "便利店"},
        ],
        "医疗": [
            {"name": f"{district}社区诊所", "distance": f"{distances['hospital']}m", "keyword": "诊所"},
            {"name": f"{district}药房", "distance": f"{max(180, distances['hospital'] - 210)}m", "keyword": "药店"},
        ],
        "美食": [
            {"name": f"{district}学生餐厅", "distance": f"{distances['dining']}m", "keyword": "餐厅"},
            {"name": f"{district}咖啡馆", "distance": f"{distances['dining'] + 95}m", "keyword": "cafe"},
        ],
        "生活": [
            {"name": f"{district}社区健身房", "distance": f"{distances['gym']}m", "keyword": "健身房"},
            {"name": f"{district}洗衣店", "distance": f"{distances['gym'] + 120}m", "keyword": "洗衣店"},
        ],
    }

    category_map = {
        "交通": "交通",
        "购物": "购物",
        "医疗": "医疗",
        "美食": "美食",
        "生活": "生活",
    }
    map_categories: dict[str, list[dict[str, Any]]] = {}
    for category, entries in poi_data.items():
        mapped: list[dict[str, Any]] = []
        for index, entry in enumerate(entries, 1):
            distance = int(str(entry["distance"]).rstrip("m"))
            mapped.append({
                "id": f"demo-{room.id}-{category}-{index}",
                "name": entry["name"],
                "lat": round(lat + (seed % 3 + index) * 0.00012, 6),
                "lng": round(lng - (seed % 4 + index) * 0.00011, 6),
                "distance": distance,
                "line": [],
            })
        map_categories[category_map[category]] = mapped

    content = (
        f"该房源位于{market['address']}。最近公共交通约{min(distances['transit'], distances['bus'])}米，"
        f"超市约{distances['supermarket']}米，诊所约{distances['hospital']}米，"
        f"健身房约{distances['gym']}米，餐饮约{distances['dining']}米。"
    )
    return content, poi_data, {
        "search_radius_m": 2000,
        "categories": map_categories,
        "source": "simulated_demo",
    }


async def _upsert_simulated_context(
    session,
    room: Property,
    market: dict[str, Any],
    university: University,
    *,
    unit_index: int,
    room_index: int,
) -> None:
    """为一间房幂等写入模拟 POI 和到目标大学的通勤数据。"""
    content, poi_data, map_poi_data = _simulated_poi_payload(room, market)
    poi = await session.scalar(
        select(PropertyPOI).where(PropertyPOI.property_id == room.id)
    )
    if poi is None:
        poi = PropertyPOI(property_id=room.id, content=content)
        session.add(poi)
    poi.content = content
    poi.poi_data = poi_data
    poi.map_poi_data = map_poi_data
    poi.generated_at = datetime.now(timezone.utc)
    poi.reviewed = False

    commute = await session.scalar(
        select(RoomCommute).where(
            RoomCommute.room_id == room.id,
            RoomCommute.university_id == university.id,
        )
    )
    if commute is None:
        commute = RoomCommute(room_id=room.id, university_id=university.id)
        session.add(commute)
    transit_base, walk_base, drive_base = COMMUTE_BASES[str(market["business_id"])]
    variation = (unit_index + room_index) % 3
    commute.transit_min = transit_base + variation
    commute.walk_min = walk_base + variation * 2
    commute.drive_min = drive_base + variation
    commute.source = "simulated_demo"
    commute.computed_at = datetime.now(timezone.utc)


async def _sync_demo_embeddings(
    session,
    unit_type_ids: list[int],
    room_ids: list[int],
) -> tuple[int, int]:
    """为尚无向量的演示户型和房间批量生成真实 embedding。"""
    from app.services.agentic.agents.search_agent import (
        build_search_text,
        build_unit_type_search_text,
    )
    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    if not service.is_available:
        print("未配置 embedding 服务，已跳过向量生成。")
        await service.close()
        return 0, 0
    try:
        unit_rows = (await session.execute(
            select(UnitType, Institute)
            .join(Institute, UnitType.institute_id == Institute.id)
            .where(
                UnitType.id.in_(unit_type_ids),
                UnitType.embedding.is_(None),
            )
            .order_by(UnitType.id)
        )).all()
        if unit_rows:
            unit_texts = [
                build_unit_type_search_text(institute, unit_type)
                for unit_type, institute in unit_rows
            ]
            unit_vectors = await service.generate_embeddings(unit_texts)
            for (unit_type, _institute), vector in zip(unit_rows, unit_vectors):
                unit_type.embedding = vector

        rooms = list(await session.scalars(
            select(Property)
            .where(
                Property.id.in_(room_ids),
                Property.embedding.is_(None),
            )
            .order_by(Property.id)
        ))
        if rooms:
            room_vectors = await service.generate_embeddings(
                [build_search_text(room) for room in rooms]
            )
            for room, vector in zip(rooms, room_vectors):
                room.embedding = vector

        await session.commit()
        return len(unit_rows), len(rooms)
    finally:
        await service.close()


async def _get_or_create_landlord(session) -> User:
    landlord = await session.scalar(select(User).where(User.username == DEMO_USERNAME))
    if landlord is None:
        landlord = User(
            username=DEMO_USERNAME,
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.landlord,
            status=UserStatus.active,
        )
        session.add(landlord)
        await session.flush()
        print(f"创建演示房东：{DEMO_USERNAME}")
    else:
        landlord.email = DEMO_EMAIL
        landlord.password_hash = hash_password(DEMO_PASSWORD)
        landlord.role = UserRole.landlord
        landlord.status = UserStatus.active
        print(f"复用演示房东：{DEMO_USERNAME}")
    return landlord


async def _upsert_universities(session) -> dict[str, University]:
    universities_by_country: dict[str, University] = {}
    for data in UNIVERSITIES:
        university = await session.scalar(
            select(University).where(University.abbreviation == data["abbreviation"])
        )
        if university is None:
            university = University(name=data["name"], latitude=data["latitude"], longitude=data["longitude"])
            session.add(university)
        for field_name, value in data.items():
            setattr(university, field_name, value)
        university.is_active = True
        university.is_hot = True
        universities_by_country[str(data["country"])] = university
    await session.flush()
    return universities_by_country


async def _upsert_market(
    session,
    landlord: User,
    market: dict,
    universities_by_country: dict[str, University],
) -> tuple[int, int, int, list[int], list[int]]:
    institute = await session.scalar(
        select(Institute).where(Institute.business_id == market["business_id"])
    )
    created_institute = 0
    if institute is None:
        institute = Institute(
            business_id=market["business_id"],
            name=market["name"],
            created_by=landlord.id,
        )
        session.add(institute)
        await session.flush()
        created_institute = 1

    for field_name in (
        "name", "name_cn", "address", "district", "city", "country",
        "amenities", "description",
    ):
        setattr(institute, field_name, market[field_name])
    institute.latitude = Decimal(market["latitude"])
    institute.longitude = Decimal(market["longitude"])
    institute.status = InstituteStatus.active

    created_units = 0
    created_rooms = 0
    unit_type_ids: list[int] = []
    room_ids: list[int] = []
    university = universities_by_country[str(market["country"])]
    for unit_index, unit_data in enumerate(market["units"], start=1):
        name, bedrooms, bathrooms, rent, area, amenities = unit_data
        unit_type = await session.scalar(
            select(UnitType).where(
                UnitType.institute_id == institute.id,
                UnitType.name == name,
                UnitType.deleted_at.is_(None),
            )
        )
        if unit_type is None:
            unit_type = UnitType(
                institute_id=institute.id,
                name=name,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                area_sqm=Decimal(area),
                base_rent=Decimal(rent),
            )
            session.add(unit_type)
            created_units += 1

        unit_type.bedrooms = bedrooms
        unit_type.bathrooms = bathrooms
        unit_type.area_sqm = Decimal(area)
        unit_type.base_rent = Decimal(rent)
        unit_type.deposit_amount = int(Decimal(rent))
        unit_type.deposit_type = DepositType.one_month
        unit_type.currency = market["currency"]
        unit_type.amenities = amenities
        unit_type.description = f"{market['name_cn']}的{name}，可拎包入住。"
        unit_type.available_from = date.today() + timedelta(days=7 * unit_index)
        unit_type.min_stay_months = 3 if unit_index == 1 else 6
        unit_type.status = UnitTypeStatus.available
        await session.flush()
        unit_type_ids.append(int(unit_type.id))

        for room_index in range(1, 3):
            room_number = f"D{institute.id:02d}-{unit_index:02d}-{room_index:02d}"
            room = await session.scalar(
                select(Property).where(
                    Property.landlord_id == landlord.id,
                    Property.room_number == room_number,
                    Property.deleted_at.is_(None),
                )
            )
            if room is None:
                room = Property(landlord_id=landlord.id, room_number=room_number)
                session.add(room)
                created_rooms += 1

            room.unit_type_id = unit_type.id
            room.institute_id = institute.id
            room.institute_name = institute.name
            room.institute_amenities = ",".join(market["amenities"])
            room.title = f"{market['name_cn']} · {name} {room_index}"
            room.description = unit_type.description
            room.address = market["address"]
            room.district = market["district"]
            room.city = market["city"]
            room.country = market["country"]
            room.currency = market["currency"]
            room.latitude = institute.latitude
            room.longitude = institute.longitude
            room.price_monthly = unit_type.base_rent
            room.deposit_amount = unit_type.deposit_amount
            room.area_sqm = unit_type.area_sqm
            room.bedrooms = bedrooms
            room.bathrooms = bathrooms
            room.property_type = (
                "studio" if bedrooms == 0 else "1-bed" if bedrooms == 1 else "2-bed"
            )
            room.available_from = unit_type.available_from
            room.min_stay_months = unit_type.min_stay_months
            room.min_lease_months = unit_type.min_stay_months
            room.max_lease_months = 12
            room.amenities = list(amenities)
            room.floor = unit_index * 2 + room_index
            room.building_block = "A" if room_index == 1 else "B"
            room.status = "available"
            await session.flush()
            room_ids.append(int(room.id))
            await _upsert_simulated_context(
                session,
                room,
                market,
                university,
                unit_index=unit_index,
                room_index=room_index,
            )

    return created_institute, created_units, created_rooms, unit_type_ids, room_ids


async def seed() -> None:
    validate_demo_catalog()
    async with async_session_maker() as session:
        landlord = await _get_or_create_landlord(session)
        universities_by_country = await _upsert_universities(session)
        totals = [0, 0, 0]
        unit_type_ids: list[int] = []
        room_ids: list[int] = []
        for market in MARKETS:
            counts = await _upsert_market(
                session,
                landlord,
                market,
                universities_by_country,
            )
            totals = [current + added for current, added in zip(totals, counts[:3])]
            unit_type_ids.extend(counts[3])
            room_ids.extend(counts[4])
            unit_count = len(market["units"])
            print(f"同步市场：{market['name_cn']}（{unit_count} 个房型、{unit_count * 2} 间房）")
        await session.commit()

        try:
            embedded_units, embedded_rooms = await _sync_demo_embeddings(
                session,
                unit_type_ids,
                room_ids,
            )
        except Exception as exc:
            embedded_units, embedded_rooms = 0, 0
            print(f"Embedding 生成失败，房源数据仍已保存：{exc}")

    print("\nAgent 演示数据已就绪")
    print(f"本次新增：{totals[0]} 个公寓、{totals[1]} 个房型、{totals[2]} 间房")
    print(f"数据覆盖：{len(room_ids)} 间房均有模拟 POI 和通勤数据")
    print(f"本次生成 embedding：{embedded_units} 个户型、{embedded_rooms} 间房")
    print(f"演示房东账号：{DEMO_USERNAME} / {DEMO_PASSWORD}")
    print("重复执行本脚本会更新同一批数据，不会重复插入。")


if __name__ == "__main__":
    asyncio.run(seed())

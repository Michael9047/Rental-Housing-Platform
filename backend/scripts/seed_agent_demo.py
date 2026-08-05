"""Agent 演示数据脚本：幂等创建测试账号、公寓、房型与可租房间。"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models.institute import Institute, InstituteStatus
from app.models.property import Property
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


async def _upsert_universities(session) -> None:
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
    await session.flush()


async def _upsert_market(session, landlord: User, market: dict) -> tuple[int, int, int]:
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
            room.status = "available"

    return created_institute, created_units, created_rooms


async def seed() -> None:
    validate_demo_catalog()
    async with async_session_maker() as session:
        landlord = await _get_or_create_landlord(session)
        await _upsert_universities(session)
        totals = [0, 0, 0]
        for market in MARKETS:
            counts = await _upsert_market(session, landlord, market)
            totals = [current + added for current, added in zip(totals, counts)]
            unit_count = len(market["units"])
            print(f"同步市场：{market['name_cn']}（{unit_count} 个房型、{unit_count * 2} 间房）")
        await session.commit()

    print("\nAgent 演示数据已就绪")
    print(f"本次新增：{totals[0]} 个公寓、{totals[1]} 个房型、{totals[2]} 间房")
    print(f"演示房东账号：{DEMO_USERNAME} / {DEMO_PASSWORD}")
    print("重复执行本脚本会更新同一批数据，不会重复插入。")


if __name__ == "__main__":
    asyncio.run(seed())

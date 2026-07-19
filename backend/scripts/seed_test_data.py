"""
种子数据脚本：创建 UCLA/NUS/NTU 等学校 + 更新房源关联
运行方式：cd backend && .venv/Scripts/python.exe scripts/seed_test_data.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from app.db.session import async_session_maker
from app.models.institute import Institute, InstituteStatus
from app.models.property import Property


INSTITUTES = [
    {
        "id": 1,
        "name": "University of California, Los Angeles (UCLA)",
        "address": "405 Hilgard Ave, Los Angeles, CA 90095",
        "description": "加州大学洛杉矶分校，美国顶尖公立研究型大学",
        "lat": 34.0689, "lng": -118.4452,
    },
    {
        "id": 2,
        "name": "National University of Singapore (NUS)",
        "address": "21 Lower Kent Ridge Rd, Singapore 119077",
        "description": "新加坡国立大学，亚洲排名第一的综合大学",
        "lat": 1.2966, "lng": 103.7764,
    },
    {
        "id": 3,
        "name": "Nanyang Technological University (NTU)",
        "address": "50 Nanyang Ave, Singapore 639798",
        "description": "南洋理工大学，新加坡最大的公立大学",
        "lat": 1.3483, "lng": 103.6831,
    },
]

# 更新现有房源：关联到已有学校
PROPERTY_UPDATES = {
    # ── UCLA 周边（已有3套）──
    45: {"institute_id": 1},  # UCLA步行3分钟
    46: {"institute_id": 1},  # UCLA南侧
    47: {"institute_id": 1},  # UCLA研究生首选 Brentwood
    # ── NUS 周边（已有3套）──
    50: {"institute_id": 2},  # NUS肯特岗 Studio
    51: {"institute_id": 2},  # NUS金文泰 HDB
    52: {"institute_id": 2},  # NUS工学院旁
    # ── NTU 周边（已有3套）──
    53: {"institute_id": 3},  # NTU云南园
    54: {"institute_id": 3},  # NTU裕廊西 HDB
    55: {"institute_id": 3},  # NTU Lakeside
    # ── 苏州 → 无学校关联 ──
    # 27-32 保持 institute_id = NULL
    # ── 伦敦 UCL ──
    33: {"institute_id": None, "country": "GB"},  # 暂不创建 UCL institute
    34: {"institute_id": None, "country": "GB"},
    35: {"institute_id": None, "country": "GB"},
    # ── 伦敦帝国理工 ──
    36: {"institute_id": None, "country": "GB"},
    37: {"institute_id": None, "country": "GB"},
    # ── 伦敦 LSE/KCL ──
    38: {"institute_id": None, "country": "GB"},
    39: {"institute_id": None, "country": "GB"},
    # ── 硅谷 Stanford ──
    40: {"institute_id": None, "country": "US"},
    41: {"institute_id": None, "country": "US"},
    42: {"institute_id": None, "country": "US"},
    # ── Berkeley ──
    43: {"institute_id": None, "country": "US"},
    44: {"institute_id": None, "country": "US"},
    # ── USC ──
    48: {"institute_id": None, "country": "US"},
    49: {"institute_id": None, "country": "US"},
    # ── 香港 ──
    56: {"institute_id": None, "country": "HK"},
    57: {"institute_id": None, "country": "HK"},
    58: {"institute_id": None, "country": "HK"},
    59: {"institute_id": None, "country": "HK"},
    60: {"institute_id": None, "country": "HK"},
    61: {"institute_id": None, "country": "HK"},
    # ── 新加坡其他（非 NUS/NTU）──
    # 已在 NUS/NTU 中覆盖
}

# 为每所学校新增 3 套（补齐到 6 套）
NEW_PROPERTIES = [
    # ═══ UCLA 补充 3 套 ═══
    {
        "title": "UCLA北门·Westwood Village一室公寓",
        "description": "位于UCLA北门Westwood Village核心区，步行5分钟进校园。一室一厅精装，配空调/洗衣机/烘干机。楼下Trader Joe's超市、In-N-Out汉堡、Starbucks，生活超级便利。适合UCLA本科生或访问学者。",
        "address": "950 Gayley Ave, Los Angeles, CA 90024",
        "district": "洛杉矶-韦斯特伍德",
        "country": "US",
        "latitude": 34.0640, "longitude": -118.4470,
        "price_monthly": 14500, "deposit_amount": 14500,
        "area_sqm": 38, "bedrooms": 1, "bathrooms": 1,
        "property_type": "apartment",
        "institute_id": 1,
    },
    {
        "title": "UCLA医学院旁·Westwood两室两卫公寓",
        "description": "位于UCLA医学院步行3分钟，两室两卫高层公寓，含泳池/健身房。Ronald Reagan Hospital对面，适合医学生/住院医师合租。全套家具家电，拎包入住。",
        "address": "10960 Wilshire Blvd, Los Angeles, CA 90024",
        "district": "洛杉矶-韦斯特伍德",
        "country": "US",
        "latitude": 34.0573, "longitude": -118.4448,
        "price_monthly": 22500, "deposit_amount": 22500,
        "area_sqm": 72, "bedrooms": 2, "bathrooms": 2,
        "property_type": "apartment",
        "institute_id": 1,
    },
    {
        "title": "UCLA南门·合租House单间（华人房东优先）",
        "description": "位于UCLA南侧Sawtelle日本城，步行12分钟到校园。独立House中一个卧室，Queen床配书桌衣柜。共享厨房客厅和后院BBQ。周边日本拉面/Daiso/Nijiya超市密集。房东优先招UCLA华人学生。",
        "address": "11300 Iowa Ave, Los Angeles, CA 90025",
        "district": "洛杉矶-西洛杉矶",
        "country": "US",
        "latitude": 34.0445, "longitude": -118.4478,
        "price_monthly": 8500, "deposit_amount": 8500,
        "area_sqm": 20, "bedrooms": 1, "bathrooms": 1,
        "property_type": "shared",
        "institute_id": 1,
    },
    # ═══ NUS 补充 3 套 ═══
    {
        "title": "NUS工程学院旁·West Coast两室公寓",
        "description": "NUS工学院步行8分钟，West Coast Plaza购物中心对面。两室一厅高层公寓，海景阳台，全家具。楼下公交5分钟直达Kent Ridge MRT。适合NUS工科研究生合租。",
        "address": "2 West Coast Walk, Singapore 127000",
        "district": "新加坡-西海岸",
        "country": "SG",
        "latitude": 1.3123, "longitude": 103.7628,
        "price_monthly": 11000, "deposit_amount": 11000,
        "area_sqm": 65, "bedrooms": 2, "bathrooms": 1,
        "property_type": "apartment",
        "institute_id": 2,
    },
    {
        "title": "NUS理学院旁·Clementi Woods精装Studio",
        "description": "NUS理学院步行6分钟，独栋公寓精装Studio。独立卫浴和小厨房，配空调/微波炉。邻近Clementi Woods公园，安静舒适，适合NUS研究生/博后单人居住。",
        "address": "88 Clementi Road, Singapore 129788",
        "district": "新加坡-金文泰",
        "country": "SG",
        "latitude": 1.3198, "longitude": 103.7701,
        "price_monthly": 7200, "deposit_amount": 7200,
        "area_sqm": 24, "bedrooms": 1, "bathrooms": 1,
        "property_type": "studio",
        "institute_id": 2,
    },
    {
        "title": "NUS商学院·Holland Village一室一厅",
        "description": "Holland Village MRT步行2分钟，到NUS商学院校车10分钟。一室一厅精装，荷兰村酒吧/餐厅/超市环绕，生活氛围极佳。适合NUS MBA/商学院学生。",
        "address": "15 Holland Drive, Singapore 278889",
        "district": "新加坡-荷兰村",
        "country": "SG",
        "latitude": 1.3110, "longitude": 103.7938,
        "price_monthly": 13000, "deposit_amount": 13000,
        "area_sqm": 42, "bedrooms": 1, "bathrooms": 1,
        "property_type": "apartment",
        "institute_id": 2,
    },
    # ═══ NTU 补充 3 套 ═══
    {
        "title": "NTU北山·研究生宿舍旁一室公寓",
        "description": "NTU North Hill宿舍区旁边，步行5分钟到SPMS/EEE学院。一室一厅精装，配空调/热水器/小厨房。楼下校车站直达校园各区域。适合NTU研究生/博后。",
        "address": "60 Nanyang Crescent, Singapore 636958",
        "district": "新加坡-裕廊西",
        "country": "SG",
        "latitude": 1.3521, "longitude": 103.6895,
        "price_monthly": 6200, "deposit_amount": 6200,
        "area_sqm": 30, "bedrooms": 1, "bathrooms": 1,
        "property_type": "apartment",
        "institute_id": 3,
    },
    {
        "title": "NTU南大通道·Jurong Point旁两室公寓",
        "description": "Jurong Point购物中心旁，Boon Lay MRT步行5分钟，到NTU校车10分钟。两室两卫高层公寓，泳池+健身房。购物/餐饮/娱乐一站式配套。适合NTU学生合租。",
        "address": "2 Jurong East Central 1, Singapore 609731",
        "district": "新加坡-文礼",
        "country": "SG",
        "latitude": 1.3415, "longitude": 103.7060,
        "price_monthly": 9800, "deposit_amount": 9800,
        "area_sqm": 68, "bedrooms": 2, "bathrooms": 2,
        "property_type": "apartment",
        "institute_id": 3,
    },
    {
        "title": "NTU NIE学院附近·Pioneer地铁站合租单间",
        "description": "Pioneer MRT步行3分钟，NTU校车5分钟进校园。三室HDB中一间Master Room，独立卫浴，配双人床/书桌/衣柜。房东直租，租金含水电网。仅限NTU学生。",
        "address": "Blk 640 Jurong West St 61, Singapore 640640",
        "district": "新加坡-裕廊西",
        "country": "SG",
        "latitude": 1.3450, "longitude": 103.6910,
        "price_monthly": 4800, "deposit_amount": 4800,
        "area_sqm": 18, "bedrooms": 1, "bathrooms": 1,
        "property_type": "shared",
        "institute_id": 3,
    },
]


async def seed():
    async with async_session_maker() as session:
        # ── 1. 创建 Institutes ──
        print("=== 创建学校 ===")
        for inst in INSTITUTES:
            existing = await session.get(Institute, inst["id"])
            if existing:
                # 更新
                existing.name = inst["name"]
                existing.address = inst["address"]
                existing.description = inst["description"]
                existing.status = InstituteStatus.active
                print(f"  更新: {inst['name'][:40]}...")
            else:
                new_inst = Institute(
                    id=inst["id"],
                    name=inst["name"],
                    address=inst["address"],
                    description=inst["description"],
                    status=InstituteStatus.active,
                    created_by=1,  # admin user
                )
                session.add(new_inst)
                print(f"  新建: {inst['name'][:40]}...")

        await session.flush()

        # ── 2. 更新现有房源 ──
        print("\n=== 更新现有房源 ===")
        for prop_id, updates in PROPERTY_UPDATES.items():
            prop = await session.get(Property, prop_id)
            if prop:
                for key, value in updates.items():
                    setattr(prop, key, value)
                print(f"  #{prop_id} {prop.title[:30]}... -> {updates}")
            else:
                print(f"  #{prop_id} NOT FOUND")

        await session.flush()

        # ── 3. 新增房源 ──
        print("\n=== 新增房源 ===")
        for data in NEW_PROPERTIES:
            prop = Property(
                landlord_id=4,  # 假设房东 ID=4
                title=data["title"],
                description=data["description"],
                address=data["address"],
                district=data["district"],
                country=data["country"],
                latitude=data["latitude"],
                longitude=data["longitude"],
                price_monthly=data["price_monthly"],
                deposit_amount=data["deposit_amount"],
                area_sqm=data["area_sqm"],
                bedrooms=data["bedrooms"],
                bathrooms=data["bathrooms"],
                property_type=data["property_type"],
                institute_id=data["institute_id"],
                status="available",
            )
            session.add(prop)
            print(f"  + {data['title'][:40]}... [{data['district']}]")

        await session.commit()
        print("\n✅ 种子数据写入完成！")


if __name__ == "__main__":
    asyncio.run(seed())

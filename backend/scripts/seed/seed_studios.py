# -*- coding: utf-8 -*-
"""Studio 房源批量补充 —— 使 studio ≈ 1-bed + 2-bed 之和
运行：cd backend && .venv/Scripts/python.exe scripts/seed/seed_studios.py
"""
import asyncio, os, sys
from decimal import Decimal
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from app.db.session import async_session_maker
from app.models.property import Property, PropertyStatus

# 各城市 Studio 分布：新加坡 30 / 伦敦 30 / 洛杉矶 15 / 香港 15 / 硅谷 5 / 伯克利 5
# = 100 套，加上现有 4 套 → 104 ≈ 103 (1-bed + 2-bed)
STUDIOS = []

# ═══ 新加坡 (NUS/NTU/SMU 周边) 30 套 ═══
sg_areas = [
    ("金文泰", 1.316, 103.766), ("荷兰村", 1.311, 103.795), ("西海岸", 1.310, 103.760),
    ("波那维斯达", 1.306, 103.790), ("杜佛", 1.303, 103.778), ("女皇镇", 1.294, 103.802),
    ("巴西班让", 1.277, 103.795), ("裕廊东", 1.333, 103.743), ("裕廊西", 1.341, 103.695),
    ("文礼", 1.338, 103.706), ("湖畔", 1.341, 103.720), ("先驱", 1.344, 103.692),
    ("武吉知马", 1.331, 103.782), ("红山", 1.285, 103.825), ("大巴窑", 1.335, 103.850),
]
for i, (area, lat, lng) in enumerate(sg_areas):
    near = "NUS" if area in ("金文泰","荷兰村","西海岸","波那维斯达","杜佛","女皇镇","巴西班让","武吉知马","红山") else "NTU"
    price = 6800 if near == "NTU" else 7800
    STUDIOS.append({
        "title": f"新加坡{area}·近{near}精装Studio",
        "description": f"位于新加坡{area}核心位置，步行5分钟到地铁站，公交/校车直达{near}。精装Studio，独立卫浴+小厨房，配空调/冰箱/洗衣机。周边食阁+超市+商场步行可达，生活便利。适合{near}留学生单人居住。",
        "address": f"Singapore {area}",
        "district": f"新加坡-{area}",
        "country": "SG", "latitude": lat + i*0.002, "longitude": lng + i*0.001,
        "price_monthly": price, "area_sqm": 28, "bedrooms": 1, "bathrooms": 1,
    })
    STUDIOS.append({
        "title": f"新加坡{area}·高校周边经济Studio",
        "description": f"新加坡{area}安静住宅区，地铁站步行8分钟。紧凑型Studio，独立卫浴，配基本家具（床+书桌+衣柜+空调）。楼下24小时便利店+公交站。价格实惠，适合预算有限的留学生。",
        "address": f"Singapore {area}",
        "district": f"新加坡-{area}",
        "country": "SG", "latitude": lat + i*0.003, "longitude": lng - i*0.002,
        "price_monthly": int(price * 0.75), "area_sqm": 22, "bedrooms": 1, "bathrooms": 1,
    })

# ═══ 伦敦 (UCL/Imperial/LSE/KCL 周边) 30 套 ═══
uk_areas = [
    ("布鲁姆斯伯里", 51.524, -0.133), ("国王十字", 51.534, -0.124), ("尤斯顿", 51.526, -0.133),
    ("南肯辛顿", 51.498, -0.175), ("伯爵宫", 51.492, -0.194), ("霍尔本", 51.517, -0.120),
    ("滑铁卢", 51.504, -0.113), ("伦敦桥", 51.505, -0.088), ("肖尔迪奇", 51.527, -0.077),
    ("卡姆登", 51.541, -0.142), ("帕丁顿", 51.517, -0.176), ("白教堂", 51.518, -0.061),
    ("金丝雀码头", 51.505, -0.020), ("汉默史密斯", 51.494, -0.225), ("伊斯灵顿", 51.536, -0.103),
]
for i, (area, lat, lng) in enumerate(uk_areas):
    if area in ("布鲁姆斯伯里","国王十字","尤斯顿"): near = "UCL"
    elif area in ("南肯辛顿","伯爵宫","汉默史密斯"): near = "Imperial"
    elif area in ("霍尔本","滑铁卢","伦敦桥"): near = "LSE/KCL"
    else: near = "伦敦各校"
    price = 12000 if near == "Imperial" else (11000 if near == "LSE/KCL" else 10500)
    STUDIOS.append({
        "title": f"伦敦{area}·近{near}精装Studio",
        "description": f"位于伦敦{area}核心区，步行/地铁直达{near}。精装Studio，独立卫浴+开放式厨房，配双人床/书桌椅/衣柜/微波炉。周边超市(Tesco/Sainsbury's)+咖啡馆+公交站步行5分钟。适合伦敦留学生单人居住。",
        "address": f"London {area}",
        "district": f"伦敦-{area}",
        "country": "GB", "latitude": lat + i*0.001, "longitude": lng + i*0.002,
        "price_monthly": price, "area_sqm": 30, "bedrooms": 1, "bathrooms": 1,
    })
    STUDIOS.append({
        "title": f"伦敦{area}·留学生经济Studio",
        "description": f"伦敦{area}安静街区，地铁站步行8分钟。紧凑型Studio，独立卫浴，基础家具齐全。周边Lidl/Aldi平价超市+公交站步行3分钟。伦敦留学生高性价比之选。",
        "address": f"London {area}",
        "district": f"伦敦-{area}",
        "country": "GB", "latitude": lat - i*0.001, "longitude": lng - i*0.001,
        "price_monthly": int(price * 0.7), "area_sqm": 22, "bedrooms": 1, "bathrooms": 1,
    })

# ═══ 洛杉矶 (UCLA/USC 周边) 15 套 ═══
la_areas = [
    ("韦斯特伍德", 34.065, -118.447), ("西洛杉矶", 34.045, -118.448), ("布伦特伍德", 34.052, -118.470),
    ("帕洛斯弗迪斯", 33.772, -118.380), ("卡尔弗城", 34.021, -118.396),
    ("南洛杉矶", 34.022, -118.285), ("韩国城", 34.060, -118.298), ("市中心", 34.045, -118.255),
]
for i, (area, lat, lng) in enumerate(la_areas):
    near = "UCLA" if area in ("韦斯特伍德","西洛杉矶","布伦特伍德") else "USC"
    STUDIOS.append({
        "title": f"洛杉矶{area}·近{near}精装Studio",
        "description": f"位于洛杉矶{area}，步行/公交直达{near}校园。精装Studio，独立卫浴+小厨房，配Queen床/书桌/衣柜/空调。周边Trader Joe's/Target+餐厅步行可达。适合{near}留学生单人住。",
        "address": f"Los Angeles {area}",
        "district": f"洛杉矶-{area}",
        "country": "US", "latitude": lat + i*0.003, "longitude": lng - i*0.002,
        "price_monthly": 9500, "area_sqm": 32, "bedrooms": 1, "bathrooms": 1,
    })

# ═══ 香港 (HKU/CUHK/CityU/PolyU 周边) 15 套 ═══
hk_areas = [
    ("西环", 22.285, 114.138), ("坚尼地城", 22.282, 114.130), ("上环", 22.286, 114.150),
    ("沙田", 22.386, 114.198), ("大围", 22.375, 114.179), ("火炭", 22.398, 114.196),
    ("九龙塘", 22.337, 114.173), ("深水埗", 22.332, 114.163), ("旺角", 22.320, 114.170),
    ("红磡", 22.305, 114.182), ("尖沙咀", 22.298, 114.173),
]
for i, (area, lat, lng) in enumerate(hk_areas):
    if area in ("西环","坚尼地城","上环"): near = "HKU"
    elif area in ("沙田","大围","火炭"): near = "CUHK"
    elif area in ("九龙塘","深水埗","旺角"): near = "CityU/BU"
    else: near = "PolyU"
    STUDIOS.append({
        "title": f"香港{area}·近{near}精装Studio",
        "description": f"位于香港{area}，地铁站步行5分钟，直达{near}。精装Studio，独立卫浴+小厨房，配双人床/书桌/衣柜/空调。周边茶餐厅+超市+地铁站步行范围。适合{near}留学生。",
        "address": f"Hong Kong {area}",
        "district": f"香港-{area}",
        "country": "HK", "latitude": lat + i*0.001, "longitude": lng + i*0.001,
        "price_monthly": 8800, "area_sqm": 20, "bedrooms": 1, "bathrooms": 1,
    })

# ═══ 硅谷 (Stanford) 5 套 ═══
sv_areas = [("帕洛阿尔托", 37.442, -122.163), ("山景城", 37.392, -122.081), ("门洛帕克", 37.456, -122.182)]
for i, (area, lat, lng) in enumerate(sv_areas):
    STUDIOS.append({
        "title": f"硅谷{area}·近Stanford精装Studio",
        "description": f"硅谷{area}，步行/骑车到Stanford校园。精装Studio，独立卫浴+小厨房，配Queen床/书桌/衣柜/空调/高速WiFi。周边Whole Foods/咖啡馆/CalTrain站步行可达。适合Stanford留学生。",
        "address": f"{area}, CA",
        "district": f"硅谷-{area}",
        "country": "US", "latitude": lat, "longitude": lng,
        "price_monthly": 16000, "area_sqm": 30, "bedrooms": 1, "bathrooms": 1,
    })

# ═══ 伯克利 5 套 ═══
bk_areas = [("伯克利市中心", 37.872, -122.260), ("北伯克利", 37.882, -122.270), ("南伯克利", 37.860, -122.255)]
for i, (area, lat, lng) in enumerate(bk_areas):
    STUDIOS.append({
        "title": f"伯克利{area}·近UC Berkeley精装Studio",
        "description": f"伯克利{area}，步行/BART到UC Berkeley校园。精装Studio，独立卫浴+小厨房，配Queen床/书桌/衣柜/暖气。周边Berkeley Bowl/Restaurant Row步行可达。适合Cal留学生。",
        "address": f"Berkeley, CA",
        "district": f"伯克利-{area}",
        "country": "US", "latitude": lat, "longitude": lng,
        "price_monthly": 14000, "area_sqm": 28, "bedrooms": 1, "bathrooms": 1,
    })


async def seed():
    async with async_session_maker() as s:
        for data in STUDIOS:
            p = Property(
                landlord_id=4,
                title=data["title"],
                description=data["description"],
                address=data["address"],
                district=data["district"],
                country=data["country"],
                latitude=Decimal(str(data["latitude"])),
                longitude=Decimal(str(data["longitude"])),
                price_monthly=data["price_monthly"],
                area_sqm=Decimal(str(data["area_sqm"])),
                bedrooms=data["bedrooms"], bathrooms=data["bathrooms"],
                property_type="studio",
                status=PropertyStatus.available.value,
            )
            s.add(p)
        await s.commit()

        from sqlalchemy import select, func
        rows = (await s.execute(
            select(Property.property_type, func.count(Property.id))
            .group_by(Property.property_type).order_by(func.count(Property.id).desc())
        )).all()
        print(f"Done: {len(STUDIOS)} studios added")
        for pt, cnt in rows:
            print(f"  {pt}: {cnt}")

asyncio.run(seed())

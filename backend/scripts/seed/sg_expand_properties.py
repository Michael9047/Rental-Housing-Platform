# -*- coding: utf-8 -*-
"""新加坡房源扩充种子脚本
- NUS 周边新增 8 套（覆盖金文泰/荷兰村/女皇镇/巴西班让等）
- NTU 周边新增 7 套（覆盖裕廊东/湖畔/先驱等）
- 偏远测试房源 5 套（榜鹅/盛港/淡滨尼/兀兰/樟宜，距两校 >15km）
运行：cd backend && .venv/Scripts/python.exe scripts/seed/sg_expand_properties.py
"""
import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from app.db.session import async_session_maker
from app.models.property import Property, PropertyStatus


# ═══════════════════════════════════════════════
# NUS 周边新增（Kent Ridge 5km 内）
# ═══════════════════════════════════════════════
NUS_PROPS = [
    # ── 金文泰 (Clementi) ──
    {
        "title": "NUS步行10分钟·金文泰地铁站旁精装HDB三房",
        "description": "金文泰地铁站步行3分钟，公交2站到NUS。HDB三室一厅，全新装修，南北通透。楼下Clementi Mall+Clementi 448市场，买菜吃饭超便利。适合NUS学生合租。",
        "address": "Blk 445 Clementi Ave 3, Singapore 120445",
        "district": "新加坡-金文泰",
        "country": "SG",
        "latitude": 1.3153, "longitude": 103.7648,
        "price_monthly": 8800, "deposit_amount": 8800,
        "area_sqm": 90, "bedrooms": 3, "bathrooms": 2,
        "property_type": "2-bed",
    },
    {
        "title": "NUS商学院·金文泰林荫道HDB主人套房",
        "description": "金文泰林荫道，步行12分钟到NUS商学院。HDB四房式中Master Room出租，独立卫浴，King床+嵌入式衣柜+书桌。房东直租，包水电网。仅限NUS学生。",
        "address": "Blk 108 Clementi St 13, Singapore 120108",
        "district": "新加坡-金文泰",
        "country": "SG",
        "latitude": 1.3198, "longitude": 103.7690,
        "price_monthly": 5800, "deposit_amount": 5800,
        "area_sqm": 22, "bedrooms": 1, "bathrooms": 1,
        "property_type": "shared",
    },
    # ── 荷兰村 (Holland Village) ──
    {
        "title": "NUS后花园·Holland Village地铁旁一室公寓",
        "description": "Holland Village MRT步行2分钟，到NUS校车8分钟。一室一厅精装公寓，开放式厨房+独立阳台。荷兰村酒吧街/超市/各国餐厅环绕，NUS学生最爱的生活区。",
        "address": "25 Holland Drive, Singapore 278889",
        "district": "新加坡-荷兰村",
        "country": "SG",
        "latitude": 1.3110, "longitude": 103.7938,
        "price_monthly": 13500, "deposit_amount": 13500,
        "area_sqm": 42, "bedrooms": 1, "bathrooms": 1,
        "property_type": "1-bed",
    },
    # ── 西海岸 (West Coast) ──
    {
        "title": "NUS工学院·West Coast Plaza斜对面两室公寓",
        "description": "NUS工学院步行6分钟，West Coast Plaza对面。两室一厅高层海景公寓，无遮挡。配全套家具家电，泳池+健身房+BBQ。适合NUS工科/理科研究生合租。",
        "address": "4 West Coast Walk, Singapore 127004",
        "district": "新加坡-西海岸",
        "country": "SG",
        "latitude": 1.3108, "longitude": 103.7610,
        "price_monthly": 10500, "deposit_amount": 10500,
        "area_sqm": 68, "bedrooms": 2, "bathrooms": 2,
        "property_type": "2-bed",
    },
    # ── 杜佛 (Dover) ──
    {
        "title": "NUS Dover地铁站旁·Polytechnic宿舍区Studio",
        "description": "Dover MRT步行4分钟，公交2站到NUS中央图书馆。精装Studio，独立卫浴+小厨房，配空调/冰箱/微波炉。安静学区内，周边绿树成荫。适合研究生单人住。",
        "address": "28 Dover Crescent, Singapore 130028",
        "district": "新加坡-杜佛",
        "country": "SG",
        "latitude": 1.3035, "longitude": 103.7785,
        "price_monthly": 6800, "deposit_amount": 6800,
        "area_sqm": 26, "bedrooms": 1, "bathrooms": 1,
        "property_type": "studio",
    },
    # ── 波那维斯达 (Buona Vista) ──
    {
        "title": "NUS北门·Buona Vista科技园一室一厅",
        "description": "Buona Vista MRT步行3分钟，公交3站到NUS。一室一厅高层公寓，落地窗采光好。楼下The Star Vista商场+One-North科技园，适合NUS计算机/商学院学生。",
        "address": "14 Rochester Park, Singapore 139205",
        "district": "新加坡-波那维斯达",
        "country": "SG",
        "latitude": 1.3068, "longitude": 103.7892,
        "price_monthly": 12500, "deposit_amount": 12500,
        "area_sqm": 40, "bedrooms": 1, "bathrooms": 1,
        "property_type": "1-bed",
    },
    # ── 巴西班让 (Pasir Panjang) ──
    {
        "title": "NUS南门·Pasir Panjang海景Studio",
        "description": "Pasir Panjang MRT步行5分钟，公交1站到NUS南门。精装Studio，独立卫浴+小厨房。高层海景，俯瞰南部山脊+港口。周边Hawker Centre步行2分钟，吃遍新加坡。",
        "address": "2 Pasir Panjang Road, Singapore 118501",
        "district": "新加坡-巴西班让",
        "country": "SG",
        "latitude": 1.2780, "longitude": 103.7938,
        "price_monthly": 7500, "deposit_amount": 7500,
        "area_sqm": 28, "bedrooms": 1, "bathrooms": 1,
        "property_type": "studio",
    },
    # ── 女皇镇 (Queenstown) ──
    {
        "title": "NUS东侧·Queenstown地铁站旁两室HDB",
        "description": "Queenstown MRT步行3分钟，到NUS公交10分钟。两室一厅HDB，新翻修，配空调/热水器/洗衣烘干机。楼下IKEA+Anchorpoint商场+Stirling View食阁，生活配套成熟。",
        "address": "Blk 153 Mei Ling St, Singapore 140153",
        "district": "新加坡-女皇镇",
        "country": "SG",
        "latitude": 1.2948, "longitude": 103.8012,
        "price_monthly": 8200, "deposit_amount": 8200,
        "area_sqm": 72, "bedrooms": 2, "bathrooms": 1,
        "property_type": "2-bed",
    },
]

# ═══════════════════════════════════════════════
# NTU 周边新增（Jurong West 5km 内）
# ═══════════════════════════════════════════════
NTU_PROPS = [
    # ── 裕廊东 (Jurong East) ──
    {
        "title": "NTU校车直达·Jurong East地铁站公寓一室一厅",
        "description": "Jurong East MRT步行2分钟，NTU校车15分钟直达。一室一厅高层公寓，含泳池/健身房/网球场。楼下JEM+Westgate+J Cube三大商场，购物/餐饮/影院一体。适合NTU学生。",
        "address": "2 Jurong East St 13, Singapore 609121",
        "district": "新加坡-裕廊东",
        "country": "SG",
        "latitude": 1.3328, "longitude": 103.7435,
        "price_monthly": 9200, "deposit_amount": 9200,
        "area_sqm": 38, "bedrooms": 1, "bathrooms": 1,
        "property_type": "1-bed",
    },
    {
        "title": "NTU Jurong East·三室HDB合租Master Room",
        "description": "Jurong East St 21，NTU校车站步行3分钟。HDB三室中Master Room，独立卫浴+Queen床+书桌+衣柜。房东是NTU校友，优先租NTU学生。包水电网。",
        "address": "Blk 239 Jurong East St 21, Singapore 600239",
        "district": "新加坡-裕廊东",
        "country": "SG",
        "latitude": 1.3390, "longitude": 103.7380,
        "price_monthly": 5200, "deposit_amount": 5200,
        "area_sqm": 20, "bedrooms": 1, "bathrooms": 1,
        "property_type": "shared",
    },
    # ── 湖畔 (Lakeside) ──
    {
        "title": "NTU Lakeside地铁站·全家具两室公寓",
        "description": "Lakeside MRT步行5分钟，NTU校车12分钟。两室两卫精装公寓，全屋家具家电，含泳池/健身房/烧烤区。面朝裕廊湖公园，安静宜居。适合NTU研究生/博后合租。",
        "address": "50 Yuan Ching Road, Singapore 618661",
        "district": "新加坡-湖畔",
        "country": "SG",
        "latitude": 1.3415, "longitude": 103.7195,
        "price_monthly": 8600, "deposit_amount": 8600,
        "area_sqm": 70, "bedrooms": 2, "bathrooms": 2,
        "property_type": "2-bed",
    },
    # ── 文礼 (Boon Lay) ──
    {
        "title": "NTU Boon Lay·Jurong Point旁精装Studio",
        "description": "Boon Lay MRT+巴士总站步行2分钟，NTU校车5分钟进校园。精装Studio，独立卫浴+小厨房。Jurong Point是新加坡最大郊区购物中心，一切生活所需步行可达。",
        "address": "10 Boon Lay Drive, Singapore 649929",
        "district": "新加坡-文礼",
        "country": "SG",
        "latitude": 1.3385, "longitude": 103.7055,
        "price_monthly": 5800, "deposit_amount": 5800,
        "area_sqm": 24, "bedrooms": 1, "bathrooms": 1,
        "property_type": "studio",
    },
    # ── 先驱 (Pioneer) ──
    {
        "title": "NTU北门Pioneer地铁站·HDB普通房出租",
        "description": "Pioneer MRT步行3分钟，NTU北门步行10分钟。三室HDB中一间普通房，配单人床/书桌椅/衣柜。共享厨房/客厅/卫生间。房东是退休教师，只租NTU学生。安静不吵闹。",
        "address": "Blk 640 Jurong West St 61, Singapore 640640",
        "district": "新加坡-先驱",
        "country": "SG",
        "latitude": 1.3440, "longitude": 103.6918,
        "price_monthly": 3500, "deposit_amount": 3500,
        "area_sqm": 14, "bedrooms": 1, "bathrooms": 1,
        "property_type": "shared",
    },
    # ── 裕廊西 (Jurong West) ──
    {
        "title": "NTU核心·Jurong West St 93四房HDB整租",
        "description": "NTU校园南侧步行15分钟，Jurong West St 93。四房式HDB整租，三室两卫+客厅+厨房+阳台。适合3-4个NTU学生合租，人均不到3000元。楼下24小时超市+食阁+Gek Poh购物。",
        "address": "Blk 928 Jurong West St 93, Singapore 640928",
        "district": "新加坡-裕廊西",
        "country": "SG",
        "latitude": 1.3418, "longitude": 103.6925,
        "price_monthly": 10800, "deposit_amount": 10800,
        "area_sqm": 110, "bedrooms": 3, "bathrooms": 2,
        "property_type": "2-bed",
    },
    # ── 裕华 (Yuhua) ──
    {
        "title": "NTU裕华园地铁旁·一室一厅安静公寓",
        "description": "Chinese Garden MRT步行4分钟，NTU校车8分钟。一室一厅低密度公寓，小区花园+泳池。窗外正对裕华园湖景，鸟语花香。适合NTU喜欢安静的研究生/博后。",
        "address": "60 Yuhua Road, Singapore 608283",
        "district": "新加坡-裕华",
        "country": "SG",
        "latitude": 1.3475, "longitude": 103.7320,
        "price_monthly": 7800, "deposit_amount": 7800,
        "area_sqm": 35, "bedrooms": 1, "bathrooms": 1,
        "property_type": "1-bed",
    },
]

# ═══════════════════════════════════════════════
# 偏远测试房源 5 套（距 NUS >15km, NTU >15km）
# ═══════════════════════════════════════════════
REMOTE_PROPS = [
    {
        "title": "【偏远测试房源#1】榜鹅水滨·Punggol Waterway两室公寓",
        "description": "⚠️ 偏远测试房源 — 距NUS约22km，距NTU约25km。位于新加坡东北端榜鹅新区，Punggol MRT+LRT步行4分钟。两室一厅高层HDB，面朝榜鹅水道公园。楼下Waterway Point商场+Safra俱乐部。适合喜欢新区的家庭，不适合NUS/NTU通勤。",
        "address": "308C Punggol Walk, Singapore 823308",
        "district": "新加坡-榜鹅",
        "country": "SG",
        "latitude": 1.4048, "longitude": 103.9028,
        "price_monthly": 7200, "deposit_amount": 7200,
        "area_sqm": 85, "bedrooms": 2, "bathrooms": 2,
        "property_type": "2-bed",
    },
    {
        "title": "【偏远测试房源#2】盛港河谷·Sengkang Rivervale HDB一室出租",
        "description": "⚠️ 偏远测试房源 — 距NUS约20km，距NTU约24km。盛港河谷Rivervale Plaza旁，LRT Rangung站2分钟。HDB四房式中Common Room，配单人床+书桌+衣柜。共用到NUS/NTU均需1小时以上通勤。适合SIT/TP学生或东北区上班族。",
        "address": "Blk 121 Rivervale Drive, Singapore 540121",
        "district": "新加坡-盛港",
        "country": "SG",
        "latitude": 1.3875, "longitude": 103.8920,
        "price_monthly": 3800, "deposit_amount": 3800,
        "area_sqm": 16, "bedrooms": 1, "bathrooms": 1,
        "property_type": "shared",
    },
    {
        "title": "【偏远测试房源#3】淡滨尼中心·Tampines Hub旁三室公寓",
        "description": "⚠️ 偏远测试房源 — 距NUS约28km，距NTU约26km。淡滨尼区域中心，Tampines MRT步行3分钟。三室两卫高级公寓，泳池/健身房/网球场齐全。楼下Tampines Hub（新加坡最大社区综合体）+3个购物中心。东部生活便利之王，但通勤NUS/NTU需1.5小时。",
        "address": "11 Tampines St 86, Singapore 528555",
        "district": "新加坡-淡滨尼",
        "country": "SG",
        "latitude": 1.3548, "longitude": 103.9438,
        "price_monthly": 9800, "deposit_amount": 9800,
        "area_sqm": 95, "bedrooms": 3, "bathrooms": 2,
        "property_type": "2-bed",
    },
    {
        "title": "【偏远测试房源#4】兀兰关口·Woodlands地铁旁整租Studio",
        "description": "⚠️ 偏远测试房源 — 距NUS约18km，距NTU约16km。兀兰区域中心，Woodlands MRT步行5分钟，直达新山关口。精装Studio，独立卫浴+小厨房。楼下Causeway Point购物中心。周末过关去JB吃喝很方便，但不适合NUS/NTU日常通勤。",
        "address": "30 Woodlands Ave 2, Singapore 738343",
        "district": "新加坡-兀兰",
        "country": "SG",
        "latitude": 1.4375, "longitude": 103.7885,
        "price_monthly": 5500, "deposit_amount": 5500,
        "area_sqm": 30, "bedrooms": 1, "bathrooms": 1,
        "property_type": "studio",
    },
    {
        "title": "【偏远测试房源#5】樟宜机场·Changi Village海边一室出租",
        "description": "⚠️ 偏远测试房源 — 距NUS约30km，距NTU约32km。新加坡最东端，樟宜村海边。一室一厅度假风公寓，阳台面朝大海。周边樟宜海滩公园+Changi Village Hawker Centre（Nasi Lemak名店）。到NUS/NTU通勤极其不便（>2小时），适合SUTD学生或樟宜机场员工。",
        "address": "5 Changi Village Road, Singapore 500005",
        "district": "新加坡-樟宜",
        "country": "SG",
        "latitude": 1.3478, "longitude": 103.9820,
        "price_monthly": 4800, "deposit_amount": 4800,
        "area_sqm": 32, "bedrooms": 1, "bathrooms": 1,
        "property_type": "1-bed",
    },
]

ALL_PROPS = NUS_PROPS + NTU_PROPS + REMOTE_PROPS


async def seed():
    async with async_session_maker() as session:
        created = 0
        for data in ALL_PROPS:
            prop = Property(
                landlord_id=4,
                title=data["title"],
                description=data["description"],
                address=data["address"],
                district=data["district"],
                country=data["country"],
                latitude=Decimal(str(data["latitude"])),
                longitude=Decimal(str(data["longitude"])),
                price_monthly=data["price_monthly"],
                deposit_amount=data["deposit_amount"],
                area_sqm=Decimal(str(data["area_sqm"])),
                bedrooms=data["bedrooms"],
                bathrooms=data["bathrooms"],
                property_type=data["property_type"],
                status=PropertyStatus.available.value,
            )
            session.add(prop)
            created += 1

        await session.commit()
        print(f"\n[OK] 新增 {created} 套新加坡房源：")
        print(f"   NUS 周边: {len(NUS_PROPS)} 套")
        print(f"   NTU 周边: {len(NTU_PROPS)} 套")
        print(f"   偏远测试: {len(REMOTE_PROPS)} 套")
        print("\n   区域覆盖：")

        remote_districts = {"新加坡-榜鹅", "新加坡-盛港", "新加坡-淡滨尼", "新加坡-兀兰", "新加坡-樟宜"}
        districts = {}
        for p in ALL_PROPS:
            d = p["district"]
            districts[d] = districts.get(d, 0) + 1
        for d, c in sorted(districts.items()):
            tag = " [偏远]" if d in remote_districts else ""
            print(f"     {d}: {c} 套{tag}")


if __name__ == "__main__":
    asyncio.run(seed())

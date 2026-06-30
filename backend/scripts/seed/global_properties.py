# -*- coding: utf-8 -*-
"""全球留学生房源种子数据脚本
为以下留学目的地的大学周边生成模拟房源：
- 英国伦敦 (UCL, Imperial, LSE, King'\''s)
- 美国硅谷 (Stanford, Berkeley)
- 美国洛杉矶 (UCLA, USC)
- 新加坡 (NUS, NTU)
- 香港 (港中文, 港大)
"""

import asyncio
import os
import sys
from pathlib import Path
from decimal import Decimal

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.user import User

# ============================================================
# 种子数据定义 — 按大学区域分组
# ============================================================

SEED_PROPERTIES = [
    # ========================
    # 伦敦 — UCL (Bloomsbury)
    # ========================
    {
        "title": "UCL步行5分钟·布鲁姆斯伯里精致一室公寓",
        "description": "位于伦敦市中心Bloomsbury核心区，步行5分钟直达UCL主校区。公寓全装修，配双人床、书桌椅、独立卫浴和开放式厨房。周边步行可达大英博物馆、罗素广场，生活便利，适合UCL/SOAS留学生。",
        "address": "35 Russell Square, Bloomsbury",
        "district": "伦敦-布鲁姆斯伯里",
        "price_monthly": Decimal("13800"),
        "area_sqm": Decimal("32"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("51.5217"), "longitude": Decimal("-0.1253"),
        "deposit_amount": 13800, "service_fee_rate": 0.10,
    },
    {
        "title": "UCL附近·国王十字车站旁两室合租公寓",
        "description": "国王十字/圣潘克拉斯车站步行3分钟，交通枢纽直达欧洲之星。两室一厅户型，主卧已出租（UCL研究生女生），现招次卧室友。客厅宽敞，带阳台，楼下Tesco Express 24小时便利。",
        "address": "12 Caledonian Road, Kings Cross",
        "district": "伦敦-国王十字",
        "price_monthly": Decimal("9600"),
        "area_sqm": Decimal("65"),
        "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "latitude": Decimal("51.5341"), "longitude": Decimal("-0.1187"),
        "deposit_amount": 9600, "service_fee_rate": 0.10,
    },
    {
        "title": "Euston站旁·UCL/CSM学生首选三室整租",
        "description": "三室一厅整租，位于Euston火车站旁，步行至UCL仅8分钟、至中央圣马丁5分钟。全新装修，配家具家电，含洗衣机/烘干机。客厅可做公共学习区。适合3人合租，人均月租约£750。",
        "address": "78 Eversholt Street, Euston",
        "district": "伦敦-尤斯顿",
        "price_monthly": Decimal("20500"),
        "area_sqm": Decimal("78"),
        "bedrooms": 3, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("51.5277"), "longitude": Decimal("-0.1334"),
        "deposit_amount": 20500, "service_fee_rate": 0.10,
    },

    # ========================
    # 伦敦 — Imperial (South Kensington)
    # ========================
    {
        "title": "帝国理工旁·南肯辛顿高端一室公寓",
        "description": "位于South Kensington富人区，步行至帝国理工主校区仅6分钟。公寓位于维多利亚式建筑内，挑高天花板、大窗采光佳。周边海德公园、V&A博物馆、哈罗德百货环绕。",
        "address": "22 Exhibition Road, South Kensington",
        "district": "伦敦-南肯辛顿",
        "price_monthly": Decimal("16500"),
        "area_sqm": Decimal("35"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "latitude": Decimal("51.4967"), "longitude": Decimal("-0.1756"),
        "deposit_amount": 16500, "service_fee_rate": 0.10,
    },
    {
        "title": "Earl'\''s Court·帝国理工步行10分钟两室",
        "description": "位于Earl'\''s Court地铁站旁，Piccadilly线直达希思罗机场。两室一厅，全装全配，含家具家电。周边餐厅超市齐全，社区安静安全，深受帝国理工/RCM留学生青睐。",
        "address": "45 Earls Court Road, Kensington",
        "district": "伦敦-伯爵宫",
        "price_monthly": Decimal("18500"),
        "area_sqm": Decimal("58"),
        "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("51.4922"), "longitude": Decimal("-0.1936"),
        "deposit_amount": 18500, "service_fee_rate": 0.10,
    },

    # ========================
    # 伦敦 — LSE / King'\''s (Holborn/Strand)
    # ========================
    {
        "title": "LSE/KCL双校圈·霍尔本Studio公寓",
        "description": "步行至LSE仅4分钟、至KCL Strand校区10分钟。精装Studio，独立厨卫，配双人床、学习桌、衣柜。楼内有24小时安保和公共洗衣房。位于Holborn核心区，Covent Garden步行可达。",
        "address": "10 Kingsway, Holborn",
        "district": "伦敦-霍尔本",
        "price_monthly": Decimal("14800"),
        "area_sqm": Decimal("28"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "latitude": Decimal("51.5153"), "longitude": Decimal("-0.1189"),
        "deposit_amount": 14800, "service_fee_rate": 0.10,
    },
    {
        "title": "Waterloo·KCL/LSE学生公寓三室",
        "description": "Waterloo地铁站步行5分钟，到KCL Waterloo校区3分钟、LSE 12分钟。三室一厅两卫，高层视野好，俯瞰泰晤士河和伦敦眼。24小时concierge，含健身房。",
        "address": "88 York Road, Waterloo",
        "district": "伦敦-滑铁卢",
        "price_monthly": Decimal("26500"),
        "area_sqm": Decimal("85"),
        "bedrooms": 3, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("51.5034"), "longitude": Decimal("-0.1133"),
        "deposit_amount": 26500, "service_fee_rate": 0.10,
    },

    # ========================
    # 硅谷 — Stanford (Palo Alto)
    # ========================
    {
        "title": "斯坦福步行距离·帕罗奥图一室公寓",
        "description": "位于Palo Alto市中心University Avenue旁，骑车8分钟/步行20分钟到斯坦福校园。一室一厅，含车位，社区安静安全。步行可达Whole Foods、CalTrain车站直达旧金山。",
        "address": "456 University Avenue, Palo Alto, CA",
        "district": "硅谷-帕罗奥图",
        "price_monthly": Decimal("18200"),
        "area_sqm": Decimal("45"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("37.4443"), "longitude": Decimal("-122.1608"),
        "deposit_amount": 18200, "service_fee_rate": 0.10,
    },
    {
        "title": "斯坦福校园旁·合租House单间（华人房东）",
        "description": "华人房东自住House分租一间卧室，步行至斯坦福工程学院仅10分钟。独立卧室配Queen床、书桌、衣柜，共享厨房客厅和后院。房东可做中餐，提供meal plan（另议）。",
        "address": "720 Stanford Avenue, Palo Alto, CA",
        "district": "硅谷-帕罗奥图",
        "price_monthly": Decimal("10200"),
        "area_sqm": Decimal("18"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "latitude": Decimal("37.4289"), "longitude": Decimal("-122.1551"),
        "deposit_amount": 10200, "service_fee_rate": 0.08,
    },
    {
        "title": "Menlo Park·斯坦福/硅谷实习生两室公寓",
        "description": "Menlo Park核心地段，靠近Meta总部和Sand Hill Road风投街。两室两卫，全装全配，带游泳池和健身房。适合斯坦福研究生或硅谷科技公司实习生合租。",
        "address": "3500 Haven Avenue, Menlo Park, CA",
        "district": "硅谷-门洛帕克",
        "price_monthly": Decimal("23800"),
        "area_sqm": Decimal("72"),
        "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("37.4847"), "longitude": Decimal("-122.1884"),
        "deposit_amount": 23800, "service_fee_rate": 0.10,
    },

    # ========================
    # 硅谷 — UC Berkeley
    # ========================
    {
        "title": "伯克利加大南门·一室一厅学生公寓",
        "description": "位于UC Berkeley南门（Southside）核心学生区，步行至校园3分钟。一室一厅，独立厨卫，楼下就是Telegraph Avenue商业街，餐厅/咖啡馆/书店密集。BART站步行8分钟直达旧金山。",
        "address": "2425 Telegraph Avenue, Berkeley, CA",
        "district": "硅谷-伯克利",
        "price_monthly": Decimal("14500"),
        "area_sqm": Decimal("40"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("37.8669"), "longitude": Decimal("-122.2591"),
        "deposit_amount": 14500, "service_fee_rate": 0.10,
    },
    {
        "title": "Berkeley Northside·安静街区两室House",
        "description": "位于伯克利北山（Northside）安静住宅区，步行至工程学院/化学学院10分钟。独立House中两室一厅，后院可BBQ，远眺金门大桥。适合研究生或访问学者家庭。",
        "address": "1825 Euclid Avenue, Berkeley, CA",
        "district": "硅谷-伯克利北山",
        "price_monthly": Decimal("19800"),
        "area_sqm": Decimal("65"),
        "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.house,
        "latitude": Decimal("37.8741"), "longitude": Decimal("-122.2615"),
        "deposit_amount": 19800, "service_fee_rate": 0.10,
    },

    # ========================
    # 洛杉矶 — UCLA (Westwood)
    # ========================
    {
        "title": "UCLA步行3分钟·韦斯特伍德精装Studio",
        "description": "位于UCLA校园西侧Westwood Village，步行3分钟进校。精装Studio，含独立卫浴和小厨房，配家具。楼下Trader Joe'\''s超市、In-N-Out汉堡，生活超级便利。",
        "address": "10911 Lindbrook Drive, Westwood, Los Angeles, CA",
        "district": "洛杉矶-韦斯特伍德",
        "price_monthly": Decimal("13200"),
        "area_sqm": Decimal("30"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "latitude": Decimal("34.0612"), "longitude": Decimal("-118.4475"),
        "deposit_amount": 13200, "service_fee_rate": 0.10,
    },
    {
        "title": "UCLA南侧·两室一厅公寓（含车位）",
        "description": "位于Wilshire Boulevard沿线，公交10分钟直达UCLA。两室一厅，含一个地下车位。社区有泳池和健身房，物业管理完善。周边Sawtelle日本城美食街步行15分钟。",
        "address": "1777 Westwood Boulevard, Los Angeles, CA",
        "district": "洛杉矶-韦斯特伍德南区",
        "price_monthly": Decimal("17500"),
        "area_sqm": Decimal("70"),
        "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("34.0507"), "longitude": Decimal("-118.4366"),
        "deposit_amount": 17500, "service_fee_rate": 0.10,
    },
    {
        "title": "UCLA研究生首选·Brentwood一室一厅",
        "description": "Brentwood高尚住宅区，距UCLA车程10分钟/公交20分钟。一室一厅独立公寓，带私人阳台，社区安静安全。周边Whole Foods、Farmers Market，适合追求生活品质的研究生/博后。",
        "address": "11930 San Vicente Boulevard, Brentwood, CA",
        "district": "洛杉矶-布伦特伍德",
        "price_monthly": Decimal("15800"),
        "area_sqm": Decimal("48"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("34.0496"), "longitude": Decimal("-118.4708"),
        "deposit_amount": 15800, "service_fee_rate": 0.10,
    },

    # ========================
    # 洛杉矶 — USC
    # ========================
    {
        "title": "USC北门·安全社区一室公寓（含门禁）",
        "description": "USC北侧安全学生社区，步行至校园5分钟，USC Village购物餐饮步行3分钟。公寓有24小时门禁和安保巡逻，配家具家电。适合USC新生/访问学者。",
        "address": "2820 S Figueroa Street, Los Angeles, CA",
        "district": "洛杉矶-大学公园",
        "price_monthly": Decimal("11200"),
        "area_sqm": Decimal("35"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("34.0261"), "longitude": Decimal("-118.2788"),
        "deposit_amount": 11200, "service_fee_rate": 0.10,
    },
    {
        "title": "USC学生合租·三室House带花园",
        "description": "USC西侧Adams-Normandie社区，Lyft/Uber 5分钟到校。独立House三室两卫，带前院和后花园。客厅宽敞配大电视，街边停车方便。已有两位USC研究生男生入住，寻第三位室友。",
        "address": "2430 S Normandie Avenue, Los Angeles, CA",
        "district": "洛杉矶-亚当斯区",
        "price_monthly": Decimal("6800"),
        "area_sqm": Decimal("95"),
        "bedrooms": 3, "bathrooms": 2,
        "property_type": PropertyType.shared,
        "latitude": Decimal("34.0321"), "longitude": Decimal("-118.3005"),
        "deposit_amount": 6800, "service_fee_rate": 0.08,
    },

    # ========================
    # 新加坡 — NUS (Kent Ridge)
    # ========================
    {
        "title": "NUS肯特岗·步行5分钟Studio公寓",
        "description": "位于Clementi/Pasir Panjang区域，步行至NUS肯特岗校区仅5分钟。Studio户型，独立厨卫，配空调、家具、高速网络。楼下食阁（Hawker Centre）步行2分钟，公交直达Clementi MRT。",
        "address": "Blk 601 Clementi West Street 1",
        "district": "新加坡-金文泰",
        "price_monthly": Decimal("6800"),
        "area_sqm": Decimal("28"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "latitude": Decimal("1.3083"), "longitude": Decimal("103.7699"),
        "deposit_amount": 6800, "service_fee_rate": 0.10,
    },
    {
        "title": "NUS附近·金文泰两室HDB整租",
        "description": "Clementi MRT步行8分钟，公交3站到NUS。HDB组屋两室一厅，高层通风好，新装修配全套家电。楼下24小时FairPrice超市，附近Clementi Mall购物方便。",
        "address": "Blk 312 Clementi Avenue 4",
        "district": "新加坡-金文泰",
        "price_monthly": Decimal("9500"),
        "area_sqm": Decimal("65"),
        "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("1.3160"), "longitude": Decimal("103.7642"),
        "deposit_amount": 9500, "service_fee_rate": 0.10,
    },
    {
        "title": "NUS工学院旁·Buona Vista公寓单间",
        "description": "Buona Vista MRT步行5分钟，一站到NUS。The Metropolitan公寓小区，泳池/健身房/BBQ台设施齐全。出租一间主卧（带独立卫浴），室友为NUS PhD男生。",
        "address": "2A Rochester Park, Buona Vista",
        "district": "新加坡-波那维斯达",
        "price_monthly": Decimal("7200"),
        "area_sqm": Decimal("22"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "latitude": Decimal("1.3059"), "longitude": Decimal("103.7878"),
        "deposit_amount": 7200, "service_fee_rate": 0.08,
    },

    # ========================
    # 新加坡 — NTU (Jurong West)
    # ========================
    {
        "title": "NTU云南园·校门口一室公寓",
        "description": "Pioneer MRT步行10分钟，NTU免费校车直达校园各角落。一室一厅公寓，新装修，配空调/热水器/洗衣机。楼下食阁和便利店，生活方便。适合NTU研究生/博后。",
        "address": "Blk 989A Jurong West Street 93",
        "district": "新加坡-裕廊西",
        "price_monthly": Decimal("5800"),
        "area_sqm": Decimal("35"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("1.3426"), "longitude": Decimal("103.6987"),
        "deposit_amount": 5800, "service_fee_rate": 0.10,
    },
    {
        "title": "NTU附近·裕廊西两室HDB合租",
        "description": "Boon Lay MRT/Jurong Point购物中心步行5分钟，公交179直达NTU。HDB两室一厅，次卧出租。房东为一对华人老夫妇（不同住），定期打扫公共区域。包水电网。",
        "address": "Blk 690D Jurong West Central 1",
        "district": "新加坡-文礼",
        "price_monthly": Decimal("4200"),
        "area_sqm": Decimal("12"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "latitude": Decimal("1.3398"), "longitude": Decimal("103.7058"),
        "deposit_amount": 4200, "service_fee_rate": 0.08,
    },
    {
        "title": "NTU校园周边·Lakeside三室公寓整租",
        "description": "Lakeside MRT步行6分钟，NTU校车20分钟。The Lakefront Residences高档公寓，三室两卫，高层湖景。小区泳池、网球场、健身房。适合NTU学生3-4人合租。",
        "address": "26 Lakeside Drive, Jurong",
        "district": "新加坡-湖畔",
        "price_monthly": Decimal("13500"),
        "area_sqm": Decimal("90"),
        "bedrooms": 3, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("1.3382"), "longitude": Decimal("103.7204"),
        "deposit_amount": 13500, "service_fee_rate": 0.10,
    },

    # ========================
    # 香港 — 港中文 CUHK (沙田/大学站)
    # ========================
    {
        "title": "港中文大学站旁·沙田一室公寓",
        "description": "大学地铁站步行3分钟，一站到港中文校园。沙田市中心一室一厅，高层山景，配空调/洗衣机/冰箱。楼下新城市广场购物餐饮一应俱全，生活极便利。",
        "address": "新界沙田安睦街28號 1座15樓A室",
        "district": "香港-沙田",
        "price_monthly": Decimal("8800"),
        "area_sqm": Decimal("25"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("22.3825"), "longitude": Decimal("114.1888"),
        "deposit_amount": 17600, "service_fee_rate": 0.10,
    },
    {
        "title": "港中文旁·大埔墟两室整租",
        "description": "大埔墟地铁站步行5分钟，一站到大学站（港中文）。洋楼两室一厅，新装修，采光好。楼下街市/超市/茶餐厅齐全，租金包含管理费和差饷。房东直租免佣。",
        "address": "新界大埔廣福道108號 2樓",
        "district": "香港-大埔",
        "price_monthly": Decimal("10500"),
        "area_sqm": Decimal("38"),
        "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("22.4489"), "longitude": Decimal("114.1670"),
        "deposit_amount": 21000, "service_fee_rate": 0.10,
    },
    {
        "title": "港中文研究生合租·火炭三室",
        "description": "火炭地铁站步行7分钟，一站到大学站。私人屋苑三室一厅两卫，会所设施含泳池/健身房。客厅宽敞可做公共学习区。已有两位港中文研究生入住，寻第三位室友（男女不限）。",
        "address": "新界火炭樂景街18號 御龍山 5座28樓B室",
        "district": "香港-火炭",
        "price_monthly": Decimal("6500"),
        "area_sqm": Decimal("72"),
        "bedrooms": 3, "bathrooms": 2,
        "property_type": PropertyType.shared,
        "latitude": Decimal("22.3962"), "longitude": Decimal("114.1985"),
        "deposit_amount": 13000, "service_fee_rate": 0.08,
    },

    # ========================
    # 香港 — 港大 HKU (西环/薄扶林)
    # ========================
    {
        "title": "港大地铁站旁·西营盘精装Studio",
        "description": "港岛线香港大学站步行2分钟，电梯直达港大校园。全新装修Studio，独立厨卫，高楼海景。周边西环码头/中山纪念公园步行可达，生活圈成熟便利。",
        "address": "香港島西環皇后大道西456號 6樓A室",
        "district": "香港-西營盤",
        "price_monthly": Decimal("10500"),
        "area_sqm": Decimal("20"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "latitude": Decimal("22.2858"), "longitude": Decimal("114.1423"),
        "deposit_amount": 21000, "service_fee_rate": 0.10,
    },
    {
        "title": "港大医学院旁·薄扶林道一室一厅",
        "description": "薄扶林道沿线，步行至港大医学院5分钟/主校区10分钟。一室一厅，高层翠绿山景，环境清幽。楼下巴士站直达中环/铜锣湾，生活与学习兼顾的理想居所。",
        "address": "香港島薄扶林道89號 寶翠園 3座12樓C室",
        "district": "香港-薄扶林",
        "price_monthly": Decimal("13000"),
        "area_sqm": Decimal("35"),
        "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("22.2788"), "longitude": Decimal("114.1366"),
        "deposit_amount": 26000, "service_fee_rate": 0.10,
    },
    {
        "title": "港大/金钟上班·坚尼地城两室海景公寓",
        "description": "坚尼地城地铁站步行3分钟，两站到港大。两室一厅，全海景阳台，新装修带全套家电。楼下海滨长廊适合跑步，咖啡店/酒吧/餐厅云集西环新美食区。港大研究生/中环金钟上班族首选。",
        "address": "香港島堅尼地城士美菲路12號 2樓B室",
        "district": "香港-堅尼地城",
        "price_monthly": Decimal("14800"),
        "area_sqm": Decimal("42"),
        "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "latitude": Decimal("22.2819"), "longitude": Decimal("114.1310"),
        "deposit_amount": 29600, "service_fee_rate": 0.10,
    },
]


async def seed_properties(dry_run: bool = False):
    """插入全球留学生房源种子数据"""
    async with async_session_maker() as session:
        # 获取可用房东
        result = await session.execute(
            select(User).where(User.role == "landlord").limit(2)
        )
        landlords = result.scalars().all()

        if not landlords:
            print("[ERROR] 没有找到房东账号，请先创建房东用户！")
            return

        landlord_ids = [l.id for l in landlords]
        print(f"找到 {len(landlords)} 个房东: {[(l.id, l.username) for l in landlords]}")
        print(f"准备插入 {len(SEED_PROPERTIES)} 条房源数据\n")

        if dry_run:
            print("=== DRY RUN MODE ===\n")
            for i, p in enumerate(SEED_PROPERTIES):
                print(f"  [{i+1}] {p['title']}")
                print(f"       地址: {p['address']}")
                print(f"       区域: {p['district']}  月租: CNY{p['price_monthly']}  坐标: ({p['latitude']}, {p['longitude']})")
                print()
            print(f"[DRY RUN] 将插入 {len(SEED_PROPERTIES)} 条房源")
            return

        # 轮询分配房东
        created = 0
        for i, pdata in enumerate(SEED_PROPERTIES):
            landlord_id = landlord_ids[i % len(landlord_ids)]
            prop = Property(
                landlord_id=landlord_id,
                status=PropertyStatus.available,
                **pdata,
            )
            session.add(prop)
            created += 1
            print(f"  [{created}] OK {pdata['title'][:40]}...")

        await session.commit()
        print(f"\n[DONE] 成功插入 {created} 条全球留学生房源！")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    asyncio.run(seed_properties(dry_run=dry))


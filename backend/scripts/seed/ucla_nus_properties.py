# -*- coding: utf-8 -*-
"""UCLA & NUS 周边差异化房源种子数据脚本
为 UCLA (洛杉矶) 和 NUS (新加坡) 各补充约 30 套合理揣测的房源，
覆盖多区域、多户型、多价位，每套房源具有独特特征。

运行方式：
  cd backend && .venv/Scripts/python.exe scripts/seed/ucla_nus_properties.py
  cd backend && .venv/Scripts/python.exe scripts/seed/ucla_nus_properties.py --dry-run
  cd backend && .venv/Scripts/python.exe scripts/seed/ucla_nus_properties.py --clear-existing
"""

import asyncio
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from sqlalchemy import select, delete
from app.db.session import async_session_maker
from app.models.property import (
    Property, PropertyType, PropertyStatus, RentType, DepositType,
)
from app.models.user import User

# ============================================================
# 种子数据定义
# ============================================================

SEED_PROPERTIES = [
    # ═══════════════════════════════════════════════════════
    # UCLA 周边 — 30 套（8 个区域）
    # ═══════════════════════════════════════════════════════

    # ── Westwood Village (5 套) — 步行到校核心区 ──
    {
        "title": "UCLA步行3分钟·Westwood Village阳光Studio",
        "description": "位于UCLA校园西侧Westwood Village核心区，步行仅3分钟进校。精装Studio，大窗朝南采光极佳，独立卫浴和小厨房，配Queen床、书桌椅、衣柜。楼下Trader Joe's超市、In-N-Out汉堡、Starbucks，生活超级便利。楼内有24小时门禁和洗衣房。适合UCLA本科生/交换生。",
        "address": "10911 Lindbrook Drive, Westwood, Los Angeles, CA 90024",
        "district": "洛杉矶-韦斯特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0612"), "longitude": Decimal("-118.4475"),
        "price_monthly": Decimal("13200"), "deposit_amount": 13200,
        "area_sqm": Decimal("30"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 3, "room_number": "301",
        "amenities": ["WiFi", "空调", "洗衣机", "24小时门禁", "家具齐全"],
        "available_from": date(2026, 8, 15),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
    },
    {
        "title": "UCLA北门·Gayley Ave一室一厅精装公寓",
        "description": "UCLA北门步行5分钟，紧邻Anderson商学院和法学院。一室一厅精装修，独立厨房配燃气灶/烤箱/冰箱，客厅宽敞可兼做学习区。卧室配双人床和步入式衣柜。楼内含健身房和包裹代收服务。步行范围内有Whole Foods超市和多家餐厅。",
        "address": "950 Gayley Avenue, Westwood, Los Angeles, CA 90024",
        "district": "洛杉矶-韦斯特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0647"), "longitude": Decimal("-118.4478"),
        "price_monthly": Decimal("16800"), "deposit_amount": 16800,
        "area_sqm": Decimal("42"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 5, "room_number": "512",
        "amenities": ["WiFi", "空调", "健身房", "代收快递", "家具齐全", "步入式衣柜"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "UCLA医学院对面·Westwood两室两卫高端公寓",
        "description": "正对Ronald Reagan UCLA Medical Center，步行至医学院/护理学院仅3分钟。两室两卫高层公寓，客厅落地窗俯瞰洛杉矶城市天际线。社区配泳池、健身房、BBQ烧烤区。主卧带独立卫浴和步入式衣柜。含一个地下车位。特别适合UCLA医学生/住院医师/访问学者合租。",
        "address": "10960 Wilshire Boulevard, Westwood, Los Angeles, CA 90024",
        "district": "洛杉矶-韦斯特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0573"), "longitude": Decimal("-118.4448"),
        "price_monthly": Decimal("23500"), "deposit_amount": 23500,
        "area_sqm": Decimal("75"), "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "floor": 12, "room_number": "1206",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "车位", "BBQ", "24小时门禁", "家具齐全"],
        "available_from": date(2026, 8, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "UCLA南门·合租House主卧（独立卫浴+阳台）",
        "description": "UCLA南侧Hilgard Ave沿线，步行7分钟到校。独立House中的主卧套房，带独立卫浴和私人阳台。Queen床、书桌、衣柜一应俱全。共享宽敞客厅、全套厨房和后院。室友为两位UCLA研究生（一男一女，安静整洁）。房东华人，可帮忙收快递、周末可搭车去华人超市。",
        "address": "545 Hilgard Avenue, Westwood, Los Angeles, CA 90024",
        "district": "洛杉矶-韦斯特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0665"), "longitude": Decimal("-118.4435"),
        "price_monthly": Decimal("9800"), "deposit_amount": 9800,
        "area_sqm": Decimal("22"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 2, "room_number": "2B",
        "amenities": ["WiFi", "空调", "阳台", "家具齐全", "独立卫浴", "后院"],
        "available_from": date(2026, 9, 10),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },
    {
        "title": "UCLA国际生首选·Wilshire合租公寓次卧",
        "description": "Wilshire Blvd高层公寓，公交5分钟/UCLA BruinBus免费校车直达校园。两室两卫户型，出租次卧（独立使用走廊对面客卫）。全家具家电，含in-unit洗衣机烘干机。室友是UCLA大三经济学女生，安静爱干净。社区有泳池和自习室。楼下公交站直达Santa Monica海滩。",
        "address": "10801 Wilshire Boulevard, Westwood, Los Angeles, CA 90024",
        "district": "洛杉矶-韦斯特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0591"), "longitude": Decimal("-118.4418"),
        "price_monthly": Decimal("8800"), "deposit_amount": 8800,
        "area_sqm": Decimal("16"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 8, "room_number": "806B",
        "amenities": ["WiFi", "空调", "泳池", "自习室", "家具齐全", "洗衣机/烘干机"],
        "available_from": date(2026, 8, 20),
        "min_stay_months": 3, "deposit_type": DepositType.half_month,
        "service_fee_rate": 0.08,
    },

    # ── Brentwood (4 套) — 高端社区，研究生/博后/访问学者 ──
    {
        "title": "Brentwood高尚社区·UCLA研究生首选一室一厅",
        "description": "Brentwood高尚住宅区，距UCLA车程10分钟/Big Blue Bus 20分钟。一室一厅独立公寓，位于安静街区，挑高天花板配大窗，采光通风极佳。含私人阳台俯瞰社区花园。步行可达Whole Foods、Farmers Market和San Vicente Blvd精品餐厅。社区设有泳池和健身房。适合追求生活品质的UCLA研究生/博后。",
        "address": "11930 San Vicente Boulevard, Brentwood, Los Angeles, CA 90049",
        "district": "洛杉矶-布伦特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0496"), "longitude": Decimal("-118.4708"),
        "price_monthly": Decimal("15800"), "deposit_amount": 15800,
        "area_sqm": Decimal("48"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 2, "room_number": "204",
        "amenities": ["WiFi", "空调", "阳台", "泳池", "健身房", "家具齐全"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Brentwood静谧Studio·UCLA访问学者长租优选",
        "description": "Brentwood Glen社区安静Studio，距UCLA车程8分钟。独栋小楼内的独立单元，配全套家具家电。社区极其安静安全，毗邻Brentwood Country Mart。步行10分钟可达Getty Center山脚步道。房东为退休UCLA教授，对访问学者特别友好，可协助办理SSN/银行开户等。最长可签3年长约。",
        "address": "1017 Bundy Drive, Brentwood, Los Angeles, CA 90049",
        "district": "洛杉矶-布伦特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0518"), "longitude": Decimal("-118.4752"),
        "price_monthly": Decimal("12500"), "deposit_amount": 12500,
        "area_sqm": Decimal("32"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "amenities": ["WiFi", "空调", "家具齐全", "独立卫浴", "车位"],
        "available_from": date(2026, 10, 1),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
        "min_lease_months": 6, "max_lease_months": 36,
    },
    {
        "title": "Brentwood家庭式·带院两室House（UCLA访问学者家庭）",
        "description": "Brentwood安静住宅区独栋House，两室一厅带前院和后花园。距UCLA车程12分钟/Big Blue Bus 25分钟。主卧Queen床+婴儿床可用，次卧可做书房/儿童房。全套厨房配中式抽油烟机和大炒锅！后院可BBQ/种菜。步行至Kenter Canyon Elementary（洛杉矶顶级公立小学）。特别适合带孩子来UCLA访学的家庭。",
        "address": "250 S Kenter Avenue, Brentwood, Los Angeles, CA 90049",
        "district": "洛杉矶-布伦特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0478"), "longitude": Decimal("-118.4810"),
        "price_monthly": Decimal("22800"), "deposit_amount": 45600,
        "area_sqm": Decimal("85"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.house,
        "amenities": ["WiFi", "空调", "车位", "后院", "全屋家电", "中式厨房"],
        "available_from": date(2026, 9, 15),
        "min_stay_months": 12, "deposit_type": DepositType.two_month,
    },
    {
        "title": "Brentwood高层·UCLA Anderson MBA景观两室公寓",
        "description": "Brentwood/San Vicente高层豪华公寓，两室两卫，客厅落地窗远眺Santa Monica山脉。距UCLA Anderson商学院车程8分钟。社区配恒温泳池、网球场、瑜伽室和共享办公空间。主卧带spa级卫浴和双人洗漱台。含两个车位。适合UCLA MBA/法学院学生合租。",
        "address": "11642 W Sunset Boulevard, Brentwood, Los Angeles, CA 90049",
        "district": "洛杉矶-布伦特伍德",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0534"), "longitude": Decimal("-118.4655"),
        "price_monthly": Decimal("26800"), "deposit_amount": 26800,
        "area_sqm": Decimal("88"), "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "floor": 15, "room_number": "1502",
        "amenities": ["WiFi", "空调", "恒温泳池", "健身房", "网球场", "共享办公空间", "双车位", "24小时前台"],
        "available_from": date(2026, 8, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },

    # ── Sawtelle (4 套) — 日本城美食街 ──
    {
        "title": "Sawtelle日本城·UCLA南侧一室一厅公寓",
        "description": "位于Sawtelle日本城核心区，步行12分钟/公交5分钟到UCLA。一室一厅精装公寓，全新装修，配in-unit洗衣机烘干机。楼下就是Sawtelle Blvd美食街——Tsujita蘸面、Daikokuya拉面、Daiso百元店、Nijiya日本超市步行2分钟。深受UCLA亚洲留学生青睐。",
        "address": "2110 Sawtelle Boulevard, Sawtelle, Los Angeles, CA 90025",
        "district": "洛杉矶-萨特尔",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0385"), "longitude": Decimal("-118.4415"),
        "price_monthly": Decimal("14500"), "deposit_amount": 14500,
        "area_sqm": Decimal("40"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 2, "room_number": "202",
        "amenities": ["WiFi", "空调", "洗衣机/烘干机", "家具齐全", "新装修"],
        "available_from": date(2026, 8, 25),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Sawtelle日式Studio·步行15分钟到UCLA",
        "description": "Sawtelle Japantown精装Studio，日式简约风装修，独立厨卫。步行至UCLA约15分钟，公交7分钟。配榻榻米风格床垫、书桌、小餐桌。楼内有共用洗衣房和自行车库。周边日式甜品店/居酒屋/漫画书店环绕，仿佛住在东京。特别适合喜欢日本文化的UCLA学生。",
        "address": "1820 S Sawtelle Boulevard, Sawtelle, Los Angeles, CA 90025",
        "district": "洛杉矶-萨特尔",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0360"), "longitude": Decimal("-118.4430"),
        "price_monthly": Decimal("10800"), "deposit_amount": 10800,
        "area_sqm": Decimal("26"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 1, "room_number": "101",
        "amenities": ["WiFi", "空调", "日式装修", "家具齐全", "自行车库"],
        "available_from": date(2026, 9, 5),
        "min_stay_months": 3, "deposit_type": DepositType.half_month,
    },
    {
        "title": "Sawtelle南区·UCLA学生合租两室公寓（主卧招租）",
        "description": "Sawtelle南侧靠近Olympic Blvd，公交8分钟直达UCLA。两室一厅公寓中主卧出租，带独立卫浴和walk-in衣柜。室友为UCLA电影学院研究生男生，平时多在学校剪辑室，家中非常安静。客厅配投影仪和PS5，可一起看电影打游戏。楼下有24小时韩国超市和深夜食堂。",
        "address": "11300 Iowa Avenue, Sawtelle, Los Angeles, CA 90025",
        "district": "洛杉矶-萨特尔",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0372"), "longitude": Decimal("-118.4470"),
        "price_monthly": Decimal("9500"), "deposit_amount": 9500,
        "area_sqm": Decimal("20"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 3, "room_number": "301M",
        "amenities": ["WiFi", "空调", "家具齐全", "独立卫浴", "投影仪"],
        "available_from": date(2026, 8, 10),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },
    {
        "title": "Sawtelle/Bundy·华人房东两室一厅整租",
        "description": "Sawtelle与Bundy交界处，公交12分钟到UCLA。两室一厅整租，华人房东自置物业，管理人员会说中文。全新装修：木地板、中央空调、石材台面厨房。配全套IKEA家具。步行至Nijiya日本超市和Marukai超市仅5分钟。房东可协助办理水电网络开户，首次来美留学无忧。",
        "address": "12100 W Olympic Boulevard, Sawtelle, Los Angeles, CA 90064",
        "district": "洛杉矶-萨特尔",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0335"), "longitude": Decimal("-118.4500"),
        "price_monthly": Decimal("18500"), "deposit_amount": 18500,
        "area_sqm": Decimal("62"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 4, "room_number": "405",
        "amenities": ["WiFi", "中央空调", "新装修", "家具齐全", "中式厨房", "华人房东"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },

    # ── Santa Monica (4 套) — 滨海生活 ──
    {
        "title": "Santa Monica海滩·UCLA通勤一室海景公寓",
        "description": "Santa Monica Ocean Avenue沿线，客厅阳台可远眺太平洋和Santa Monica Pier。距UCLA车程15分钟/Big Blue Bus 1号线30分钟直达校园。一室一厅精装，全新厨房配石英台面和不锈钢电器。楼下Palasades Park海滨步道，适合晨跑/骑行。周末步行即可享受海滩生活。适合注重work-life balance的UCLA研究生。",
        "address": "1033 Ocean Avenue, Santa Monica, CA 90401",
        "district": "洛杉矶-圣莫尼卡",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0198"), "longitude": Decimal("-118.4982"),
        "price_monthly": Decimal("19800"), "deposit_amount": 19800,
        "area_sqm": Decimal("50"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 6, "room_number": "601",
        "amenities": ["WiFi", "空调", "海景阳台", "健身房", "车位", "家具齐全"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Santa Monica Downtown·UCLA交换生Studio短租",
        "description": "Santa Monica Downtown核心区，步行至Third Street Promenade步行街和Santa Monica Place购物中心仅3分钟。精装Studio，独立厨卫，配家具。Big Blue Bus直达UCLA约35分钟。楼下有Blue Bottle Coffee和多家Brunch餐厅。适合短期交换/暑期项目的UCLA学生，可月租。",
        "address": "401 Broadway, Santa Monica, CA 90401",
        "district": "洛杉矶-圣莫尼卡",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0165"), "longitude": Decimal("-118.4945"),
        "price_monthly": Decimal("11500"), "deposit_amount": 5750,
        "area_sqm": Decimal("28"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 2, "room_number": "208",
        "amenities": ["WiFi", "空调", "家具齐全", "短租支持"],
        "available_from": date(2026, 7, 15),
        "min_stay_months": 1, "deposit_type": DepositType.half_month,
        "min_lease_months": 1,
    },
    {
        "title": "Santa Monica Montana Ave·两室House（UCLA家庭）",
        "description": "Santa Monica Montana Avenue高尚社区，独栋两室House带私人车库和庭院。距UCLA车程12分钟。Montana Ave沿线精品店/咖啡馆/有机超市闻名洛杉矶。社区小学Franklin Elementary为LA顶级公立学校。主卧Queen床、次卧可做儿童房或书房。适合UCLA教授/访问学者家庭长租。",
        "address": "1007 Montana Avenue, Santa Monica, CA 90403",
        "district": "洛杉矶-圣莫尼卡",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0280"), "longitude": Decimal("-118.4970"),
        "price_monthly": Decimal("25800"), "deposit_amount": 51600,
        "area_sqm": Decimal("90"), "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.house,
        "amenities": ["WiFi", "空调", "私人车库", "庭院", "全屋家电", "学区房"],
        "available_from": date(2026, 10, 1),
        "min_stay_months": 12, "deposit_type": DepositType.two_month,
    },
    {
        "title": "Santa Monica合租三室·UCLA艺术学院学生社区",
        "description": "Santa Monica Pico Blvd沿线三室House，已有两位UCLA艺术学院研究生入住（一位电影、一位设计），现招第三位室友。独立次卧配单人床/书桌/衣柜。共享空间有：配备投影仪的客厅、艺术工作室（可做画室/摄影暗房）、后院花园。社区安静有创意氛围，步行可达Bergamot Station艺术区。",
        "address": "2633 Pico Boulevard, Santa Monica, CA 90405",
        "district": "洛杉矶-圣莫尼卡",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0228"), "longitude": Decimal("-118.4690"),
        "price_monthly": Decimal("7800"), "deposit_amount": 7800,
        "area_sqm": Decimal("14"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "amenities": ["WiFi", "空调", "后院", "艺术工作室", "投影仪"],
        "available_from": date(2026, 8, 5),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },

    # ── Culver City (4 套) — 科技/创意区 ──
    {
        "title": "Culver City科技区·UCLA通勤一室精装公寓",
        "description": "Culver City Downtown科技/创意区，Google/Apple/Amazon办公室环绕。距UCLA车程15分钟/CCE公交25分钟。一室一厅工业风loft，挑高4米、水泥墙面、大窗采光。配全套家具家电。步行可达Platform创意商圈、Culver Steps美食广场。适合UCLA CS/工程学院实习期学生。",
        "address": "8850 Washington Boulevard, Culver City, CA 90232",
        "district": "洛杉矶-卡尔弗城",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0265"), "longitude": Decimal("-118.3890"),
        "price_monthly": Decimal("15200"), "deposit_amount": 15200,
        "area_sqm": Decimal("45"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 3, "room_number": "301",
        "amenities": ["WiFi", "空调", "Loft挑高", "家具齐全", "健身房"],
        "available_from": date(2026, 8, 20),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Culver City Hayden Tract·创意Studio短租",
        "description": "Culver City Hayden Tract创意园区内，由著名建筑师Eric Owen Moss设计的特色建筑。精装Studio，独立厨卫，超大窗户配智能百叶窗。社区内有多家网红咖啡店/精酿酒吧/艺术画廊。距UCLA车程18分钟。适合暑期在LA科技公司实习的UCLA学生，支持1-3个月短租。",
        "address": "3525 Hayden Avenue, Culver City, CA 90232",
        "district": "洛杉矶-卡尔弗城",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0240"), "longitude": Decimal("-118.3825"),
        "price_monthly": Decimal("13800"), "deposit_amount": 6900,
        "area_sqm": Decimal("34"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 1, "room_number": "101",
        "amenities": ["WiFi", "空调", "设计建筑", "智能家居", "短租支持"],
        "available_from": date(2026, 7, 1),
        "min_stay_months": 1, "deposit_type": DepositType.half_month,
        "min_lease_months": 1, "max_lease_months": 3,
    },
    {
        "title": "Culver City/Palms交界·UCLA学生两室合租",
        "description": "Culver City与Palms交界处，Expo Line地铁站步行5分钟，地铁15分钟到UCLA（Westwood站）。两室一厅公寓，次卧出租，室友为UCLA经济学PhD一年级男生。全家具家电，含in-unit洗衣烘干机。社区安静，楼下是Trader Joe's超市。适合需要安静学习环境的研究生。",
        "address": "3700 Overland Avenue, Palms, Los Angeles, CA 90034",
        "district": "洛杉矶-卡尔弗城",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0225"), "longitude": Decimal("-118.4085"),
        "price_monthly": Decimal("8500"), "deposit_amount": 8500,
        "area_sqm": Decimal("15"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 2, "room_number": "2B",
        "amenities": ["WiFi", "空调", "洗衣机/烘干机", "家具齐全", "近地铁"],
        "available_from": date(2026, 9, 15),
        "min_stay_months": 12, "deposit_type": DepositType.half_month,
        "service_fee_rate": 0.08,
    },
    {
        "title": "Culver City Downtown·两室两卫豪华公寓（UCLA商学院）",
        "description": "Culver City Downtown核心位置，步行至Culver Steps购物餐饮区。两室两卫全新豪华公寓，配中央空调、Nest智能温控、石英台面厨房。社区设施：无边泳池、户外影院、共享办公空间、宠物SPA。Expo Line地铁站步行7分钟，地铁20分钟到UCLA。含两个车位。适合UCLA MBA/法学院学生高端合租。",
        "address": "9300 Culver Boulevard, Culver City, CA 90232",
        "district": "洛杉矶-卡尔弗城",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0238"), "longitude": Decimal("-118.3934"),
        "price_monthly": Decimal("24800"), "deposit_amount": 24800,
        "area_sqm": Decimal("82"), "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "floor": 7, "room_number": "712",
        "amenities": ["WiFi", "中央空调", "无边泳池", "健身房", "共享办公", "双车位", "宠物友好", "智能家居"],
        "available_from": date(2026, 8, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },

    # ── Century City (3 套) — 高端商务区 ──
    {
        "title": "Century City天际线·UCLA北侧一室豪华公寓",
        "description": "Century City核心区高端公寓，落地窗俯瞰洛杉矶天际线和好莱坞山。距UCLA车程仅8分钟/Santa Monica Blvd公交15分钟。一室一厅配全套设计师家具，开放式厨房配Miele电器。社区提供24小时doorman、恒温泳池、私人影院和品酒室。步行至Westfield Century City购物中心。适合追求极致品质的UCLA研究生。",
        "address": "1 W Century Drive, Century City, Los Angeles, CA 90067",
        "district": "洛杉矶-世纪城",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0584"), "longitude": Decimal("-118.4145"),
        "price_monthly": Decimal("21000"), "deposit_amount": 21000,
        "area_sqm": Decimal("55"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 18, "room_number": "1803",
        "amenities": ["WiFi", "中央空调", "天际线景观", "恒温泳池", "健身房", "24小时门房", "私人影院", "设计师家具"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Century City商务Studio·UCLA Anderson实习期短租",
        "description": "Century City商务区精装Studio，周边顶级投行/咨询/律所环绕。距UCLA Anderson商学院车程5分钟。全配高端家具：Herman Miller办公椅、升降桌、4K显示器。社区有商务中心和会议室可预约使用。适合在Century City/Westwood实习的UCLA商学院/法学院学生。支持3-6个月短租。",
        "address": "1880 Century Park East, Century City, Los Angeles, CA 90067",
        "district": "洛杉矶-世纪城",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0605"), "longitude": Decimal("-118.4132"),
        "price_monthly": Decimal("17500"), "deposit_amount": 8750,
        "area_sqm": Decimal("38"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 10, "room_number": "1005",
        "amenities": ["WiFi", "中央空调", "商务中心", "健身房", "设计师家具", "4K显示器", "升降桌", "短租支持"],
        "available_from": date(2026, 7, 15),
        "min_stay_months": 3, "deposit_type": DepositType.half_month,
        "min_lease_months": 3,
    },
    {
        "title": "Century City两室公寓·UCLA法学院/Anderson合租首选",
        "description": "Century City/Westwood交界处，步行至UCLA法学院和Anderson商学院仅12分钟。两室两卫高层公寓，客厅和主卧均享Century City天际线景观。社区配网球场、桑拿房、红酒窖。楼下即Westfield Century City（洛杉矶顶级购物中心），Eataly意大利美食广场步行2分钟。含两车位。",
        "address": "10250 Santa Monica Boulevard, Century City, Los Angeles, CA 90067",
        "district": "洛杉矶-世纪城",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0592"), "longitude": Decimal("-118.4180"),
        "price_monthly": Decimal("28000"), "deposit_amount": 28000,
        "area_sqm": Decimal("85"), "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "floor": 22, "room_number": "2201",
        "amenities": ["WiFi", "中央空调", "天际线景观", "健身房", "网球场", "桑拿", "双车位", "24小时门房"],
        "available_from": date(2026, 8, 15),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },

    # ── Palms (3 套) — 经济实惠 ──
    {
        "title": "Palms实惠一室·Expo线地铁直达UCLA",
        "description": "Palms核心区经济实惠一室公寓，Expo Line Palms站步行5分钟，地铁15分钟直达UCLA Westwood站。麻雀虽小五脏俱全：独立卫浴、小厨房、双人床、书桌。楼下有Ralphs超市、24小时便利店和多家平价餐厅。社区多元友好，深受UCLA预算敏感型学生欢迎。租金含水费和垃圾费。",
        "address": "3500 Overland Avenue, Palms, Los Angeles, CA 90034",
        "district": "洛杉矶-帕姆斯",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0255"), "longitude": Decimal("-118.4122"),
        "price_monthly": Decimal("7800"), "deposit_amount": 7800,
        "area_sqm": Decimal("32"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 1, "room_number": "103",
        "amenities": ["WiFi", "空调", "近地铁", "家具齐全", "包水费"],
        "available_from": date(2026, 8, 10),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Palms合租两室·次卧$800全包（UCLA本科生）",
        "description": "Palms安静社区两室公寓，次卧招租。Expo Line地铁站步行8分钟，到UCLA全程20分钟。室友为UCLA大三CS本科生男生，平时多在学校lab。全包价含水电网煤气，真正的拎包入住。卧室配床/书桌/衣柜/台灯/小米空气净化器。客厅有PS5和Switch可共用。楼下街边停车方便（需permit）。",
        "address": "3650 Keystone Avenue, Palms, Los Angeles, CA 90034",
        "district": "洛杉矶-帕姆斯",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0240"), "longitude": Decimal("-118.4165"),
        "price_monthly": Decimal("5800"), "deposit_amount": 5800,
        "area_sqm": Decimal("14"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 2, "room_number": "2B",
        "amenities": ["WiFi", "空调", "包水电", "家具齐全", "近地铁", "PS5"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },
    {
        "title": "Palms/Motor Ave·新装修两室一厅整租",
        "description": "Palms东侧Motor Avenue沿线，Expo Line Culver City站步行6分钟。两室一厅新装修公寓，全屋木地板、新空调、新厨房电器。两个卧室均配Queen床和书桌，客厅配沙发/电视/餐桌。社区有多家韩国餐厅和Spa。UCLA通勤：地铁Expo Line约18分钟。适合两个UCLA学生整租，人均月租不到¥6000。",
        "address": "10445 Motor Avenue, Palms, Los Angeles, CA 90034",
        "district": "洛杉矶-帕姆斯",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0275"), "longitude": Decimal("-118.4078"),
        "price_monthly": Decimal("12500"), "deposit_amount": 12500,
        "area_sqm": Decimal("58"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 3, "room_number": "305",
        "amenities": ["WiFi", "空调", "新装修", "家具齐全", "近地铁", "木地板"],
        "available_from": date(2026, 9, 15),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },

    # ── Mar Vista (3 套) — 安静住宅区 ──
    {
        "title": "Mar Vista安静社区·UCLA博后一室独立小屋",
        "description": "Mar Vista安静住宅区内独立后屋（Back House），完全独立入口，不与主屋共享任何空间。一室一厅配全套家具家电。社区极其安静，以家庭住户为主，适合专注研究的UCLA博后/访问学者。步行至Mar Vista Recreation Center公园和社区图书馆。公交15分钟/Car 10分钟到UCLA。含一个专用车位。房东为退休UCLA教授。",
        "address": "3750 Beethoven Street, Mar Vista, Los Angeles, CA 90066",
        "district": "洛杉矶-马维斯塔",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0065"), "longitude": Decimal("-118.4360"),
        "price_monthly": Decimal("13500"), "deposit_amount": 13500,
        "area_sqm": Decimal("38"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "amenities": ["WiFi", "空调", "专用车位", "独立入口", "家具齐全", "安静社区"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Mar Vista家庭House·三室带泳池（UCLA访问学者）",
        "description": "Mar Vista核心区独栋House，三室两卫，带私人泳池和后院。距UCLA车程15分钟。主卧套房配King床和spa浴缸，两个次卧均配Queen床和书桌。开放式厨房配双开门冰箱和6头燃气灶。后院有BBQ烧烤台和橙子树/柠檬树。社区小学Mar Vista Elementary步行5分钟。适合UCLA访问学者/博后带家人入住。",
        "address": "3325 Mountain View Avenue, Mar Vista, Los Angeles, CA 90066",
        "district": "洛杉矶-马维斯塔",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0090"), "longitude": Decimal("-118.4320"),
        "price_monthly": Decimal("28000"), "deposit_amount": 56000,
        "area_sqm": Decimal("120"), "bedrooms": 3, "bathrooms": 2,
        "property_type": PropertyType.house,
        "amenities": ["WiFi", "中央空调", "私人泳池", "后院", "BBQ", "双车位", "全屋家电", "学区房"],
        "available_from": date(2026, 10, 1),
        "min_stay_months": 12, "deposit_type": DepositType.two_month,
    },
    {
        "title": "Mar Vista/Penmar·UCLA通勤Studio小屋",
        "description": "Mar Vista Penmar高尔夫球场旁安静Studio。独立小屋配独立入口、厨卫和家具。超大后院可晒太阳/看书/做瑜伽。Penmar Park步行2分钟。Venice Blvd公交25分钟直达UCLA。距Venice Beach车程仅8分钟，周末冲浪/骑行超方便。适合喜欢户外运动/安静独处的UCLA研究生。",
        "address": "12444 Venice Boulevard, Mar Vista, Los Angeles, CA 90066",
        "district": "洛杉矶-马维斯塔",
        "country": "US", "institute_id": 1,
        "latitude": Decimal("34.0035"), "longitude": Decimal("-118.4385"),
        "price_monthly": Decimal("10800"), "deposit_amount": 10800,
        "area_sqm": Decimal("25"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "amenities": ["WiFi", "空调", "后院", "独立入口", "家具齐全", "近海滩"],
        "available_from": date(2026, 8, 20),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
    },

    # ═══════════════════════════════════════════════════════
    # NUS 周边 — 30 套（8 个区域）
    # ═══════════════════════════════════════════════════════

    # ── Clementi (5 套) — 最近 NUS，学生聚集区 ──
    {
        "title": "NUS肯特岗·Clementi MRT旁Studio精装公寓",
        "description": "Clementi MRT步行3分钟，公交3站直达NUS肯特岗校区。精装Studio，独立厨卫，配空调/热水器/迷你冰箱。高层通风好，窗外绿树成荫。楼下Clementi Mall购物中心、FairPrice超市、食阁一应俱全。适合NUS本科生/研究生单人居住，生活超级便利。",
        "address": "Blk 601 Clementi West Street 1, #15-03, Singapore 120601",
        "district": "新加坡-金文泰",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3083"), "longitude": Decimal("103.7699"),
        "price_monthly": Decimal("6800"), "deposit_amount": 6800,
        "area_sqm": Decimal("28"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 15, "room_number": "15-03",
        "amenities": ["WiFi", "空调", "家具齐全", "近地铁", "独立卫浴"],
        "available_from": date(2026, 8, 5),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
    },
    {
        "title": "NUS附近·Clementi Ave 4高层HDB两室整租",
        "description": "Clementi Avenue 4沿线，高层HDB组屋两室一厅。步行至Clementi MRT 8分钟，公交96路5分钟到NUS工学院。全装修配全套家电：空调×3、洗衣机、冰箱、热水器。楼下24小时FairPrice超市和湿巴刹，买菜做饭超方便。屋主直租免中介费，可登记HDB（符合新加坡外籍学生租房规定）。",
        "address": "Blk 312 Clementi Avenue 4, #22-05, Singapore 120312",
        "district": "新加坡-金文泰",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3160"), "longitude": Decimal("103.7642"),
        "price_monthly": Decimal("9500"), "deposit_amount": 9500,
        "area_sqm": Decimal("65"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 22, "room_number": "22-05",
        "amenities": ["WiFi", "空调", "全屋家电", "近地铁", "近超市", "高层通风"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "NUS Science Park旁·Clementi Woods两室Condo",
        "description": "Clementi Woods Park旁边的私人公寓（Condo），两室一厅精装。小区设施：泳池、健身房、网球场、BBQ台。步行至NUS Science Park/NUH医院仅8分钟，特别适合NUS医学院/理学院学生。Clementi MRT步行12分钟/小区免费shuttle bus。安静且配套完善。",
        "address": "88 Clementi Road, The Rochester #08-02, Singapore 129788",
        "district": "新加坡-金文泰",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3098"), "longitude": Decimal("103.7721"),
        "price_monthly": Decimal("11500"), "deposit_amount": 11500,
        "area_sqm": Decimal("68"), "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "floor": 8, "room_number": "08-02",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "网球场", "BBQ", "家具齐全"],
        "available_from": date(2026, 9, 10),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "NUS工学院·Clementi HDB合租Master Room",
        "description": "Clementi Ave 3五房式HDB，Master Room（主卧带独立卫浴）出租。室友为NUS工学院PhD学生（一男一女couple），安静整洁。步行至NUS工学院仅8分钟！全配空调、King床、书桌、大衣柜和独立卫生间。客厅宽敞可共用，厨房设备齐全。楼下食阁/杂货店/诊所，生活极其便利。屋主不同住。",
        "address": "Blk 430 Clementi Avenue 3, #10-07, Singapore 120430",
        "district": "新加坡-金文泰",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3125"), "longitude": Decimal("103.7688"),
        "price_monthly": Decimal("6200"), "deposit_amount": 6200,
        "area_sqm": Decimal("20"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 10, "room_number": "10-MBR",
        "amenities": ["WiFi", "空调", "独立卫浴", "家具齐全", "近校园", "包水电"],
        "available_from": date(2026, 8, 15),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },
    {
        "title": "NUS商学院旁·Clementi新Condo一室一厅",
        "description": "Clementi最新建成的高端Condo（Clavon），一室一厅精装。距NUS商学院车程5分钟/公交10分钟。全屋智能家居（智能空调/灯光/门锁），配名牌家电（Bosch洗衣机/Samsung冰箱）。小区设施顶级：50米天际泳池、空中健身房、共享厨房（可预约办party）。适合NUS MBA/商学院高端学生或年轻教职工。",
        "address": "2 Clementi Avenue 1, Clavon #18-05, Singapore 129955",
        "district": "新加坡-金文泰",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3195"), "longitude": Decimal("103.7620"),
        "price_monthly": Decimal("14000"), "deposit_amount": 14000,
        "area_sqm": Decimal("48"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 18, "room_number": "18-05",
        "amenities": ["WiFi", "中央空调", "天际泳池", "空中健身房", "智能家居", "共享厨房", "24小时门禁"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },

    # ── Buona Vista (4 套) — 科技园区，设施高端 ──
    {
        "title": "Buona Vista·The Metropolitan一室Condo（NUS校车直达）",
        "description": "Buona Vista MRT步行4分钟，NUS免费校车A1线直达校园。The Metropolitan高端Condo一室一厅。小区设施：无边泳池、网球场、壁球馆、烧烤区、多功能厅。全家具家电，客厅配55寸电视。楼下The Star Vista购物中心（餐厅/超市/影院），One-North科技园步行5分钟。适合NUS研究生/One-North实习生。",
        "address": "2A Rochester Park, The Metropolitan #12-03, Singapore 139228",
        "district": "新加坡-波那维斯达",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3062"), "longitude": Decimal("103.7885"),
        "price_monthly": Decimal("12800"), "deposit_amount": 12800,
        "area_sqm": Decimal("52"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 12, "room_number": "12-03",
        "amenities": ["WiFi", "空调", "无边泳池", "健身房", "网球场", "家具齐全", "近地铁", "校车直达"],
        "available_from": date(2026, 8, 10),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Buona Vista·One-North科技园两室Condo（NUS CS学生）",
        "description": "One-North科技园区内高端Condo两室一厅，距NUS计算机学院校车10分钟。周边Grab/Shopee/Google等科技公司环绕，internship通勤零距离。两室配双人床和书桌，客厅落地窗View好。小区配套：Lap Pool/健身房/共享办公空间（有打印机和会议室）。特别适合NUS SoC/工学院学生合租。",
        "address": "1 Fusionopolis Walk, One-North Residences #09-02, Singapore 138577",
        "district": "新加坡-波那维斯达",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3038"), "longitude": Decimal("103.7870"),
        "price_monthly": Decimal("15500"), "deposit_amount": 15500,
        "area_sqm": Decimal("72"), "bedrooms": 2, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "floor": 9, "room_number": "09-02",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "共享办公", "智能家居", "24小时门禁"],
        "available_from": date(2026, 9, 5),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Buona Vista·NUS杨潞龄医学院旁精装Studio",
        "description": "紧邻NUS杨潞龄医学院和NUH（国立大学医院），步行仅5分钟。精装Studio，独立卫浴，配微波炉/迷你冰箱/电热水壶。整栋楼为医疗/科研人员为主，安静专业。Buona Vista MRT步行10分钟。适合NUS医学院/NUH实习生/住院医师单人住。",
        "address": "10 Medical Drive, Singapore 117597",
        "district": "新加坡-波那维斯达",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3000"), "longitude": Decimal("103.7845"),
        "price_monthly": Decimal("7500"), "deposit_amount": 7500,
        "area_sqm": Decimal("26"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 3, "room_number": "03-01",
        "amenities": ["WiFi", "空调", "独立卫浴", "近医院", "安静社区"],
        "available_from": date(2026, 8, 20),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Buona Vista·Ghim Moh Link五房HDB合租（NUS室友）",
        "description": "Ghim Moh Link五房式HDB（稀有大地板），宽敞客厅配大沙发和65寸电视。现有一间Common Room招租，两位室友为NUS工学院和理学院研究生。屋主为华人老夫妇不同住，每月过来一次检查。楼下Ghim Moh Market & Food Centre（新加坡著名平价美食中心）步行2分钟。Buona Vista MRT步行8分钟。包水电网。",
        "address": "Blk 24 Ghim Moh Link, #16-03, Singapore 270024",
        "district": "新加坡-波那维斯达",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3092"), "longitude": Decimal("103.7935"),
        "price_monthly": Decimal("4800"), "deposit_amount": 4800,
        "area_sqm": Decimal("13"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 16, "room_number": "16-CR",
        "amenities": ["WiFi", "空调", "包水电", "家具齐全", "近美食中心", "近地铁"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },

    # ── Holland Village (4 套) — 咖啡馆/酒吧/外籍人士区 ──
    {
        "title": "Holland Village·NUS商学院/法学院一室一厅Condo",
        "description": "Holland Village MRT步行1分钟！到NUS法学院/商学院校车仅8分钟。Holland Village是新加坡最具活力的外籍人士/学生聚集区，整条街布满精品咖啡馆/酒吧/各国餐厅。一室一厅精装Condo，配全套设计师家具。小区有泳池/健身房。周末下楼就是Brunch和Night Market。适合社交活跃的NUS MBA/法学院学生。",
        "address": "15 Holland Drive, Holland Residences #10-01, Singapore 278889",
        "district": "新加坡-荷兰村",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3110"), "longitude": Decimal("103.7945"),
        "price_monthly": Decimal("14500"), "deposit_amount": 14500,
        "area_sqm": Decimal("45"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 10, "room_number": "10-01",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "设计师家具", "近地铁", "近商圈"],
        "available_from": date(2026, 8, 15),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Holland Village·Loft风格Studio（NUS交换生最爱）",
        "description": "Holland Village核心区Loft风格Studio，挑高4.2米，上下两层（上层卧室、下层客厅+厨房）。全配设计师家具和艺术品。出门左转即Holland Village酒吧街和Craftsmen Specialty Coffee。NUS校车B线10分钟直达Kent Ridge。适合来NUS交换/短期访学的学生，享受新加坡最具Boho风情社区的生活。支持最短3个月租期。",
        "address": "28 Lorong Mambong, Holland Village, Singapore 277678",
        "district": "新加坡-荷兰村",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3102"), "longitude": Decimal("103.7960"),
        "price_monthly": Decimal("10800"), "deposit_amount": 10800,
        "area_sqm": Decimal("30"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 2, "room_number": "02-01",
        "amenities": ["WiFi", "空调", "Loft挑高", "设计师家具", "短租支持", "近商圈"],
        "available_from": date(2026, 8, 1),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Holland Village·两室Condo合租（主卧+书房）",
        "description": "Holland Village附近高端Condo两室户型，出租主卧套房（含独立卫浴+小书房）。室友为NUS法学院LLM女生，安静整洁（大部分时间在学校图书馆）。全屋家具为MUJI风格，简洁舒适。小区有50米泳池和空中花园。步行至Holland Village MRT 5分钟。适合喜欢安静但又要社交便利的NUS研究生。",
        "address": "50 Holland Road, Leedon Residence #08-05, Singapore 258855",
        "district": "新加坡-荷兰村",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3090"), "longitude": Decimal("103.7990"),
        "price_monthly": Decimal("9800"), "deposit_amount": 9800,
        "area_sqm": Decimal("22"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 8, "room_number": "08-MBR",
        "amenities": ["WiFi", "空调", "独立卫浴", "书房", "泳池", "空中花园", "MUJI家具"],
        "available_from": date(2026, 9, 10),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },
    {
        "title": "Holland Village·豪华一室Condo（NUS教职工/博后）",
        "description": "Holland Road沿线低密度豪华Condo，一室一厅配超大阳台。小区仅80户，极其安静私密。配高端家电（Miele/Smeg），实木地板，落地窗通透明亮。物业提供每周一次免费保洁。步行至Holland Village 8分钟/Dempsey Hill餐饮区10分钟。适合NUS年轻教授/博后/高级访问学者。",
        "address": "58 Holland Road, D'Leedon #15-02, Singapore 258866",
        "district": "新加坡-荷兰村",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3070"), "longitude": Decimal("103.8010"),
        "price_monthly": Decimal("16000"), "deposit_amount": 32000,
        "area_sqm": Decimal("55"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 15, "room_number": "15-02",
        "amenities": ["WiFi", "中央空调", "阳台", "泳池", "健身房", "高端家电", "免费保洁", "低密度"],
        "available_from": date(2026, 10, 1),
        "min_stay_months": 12, "deposit_type": DepositType.two_month,
    },

    # ── Pasir Panjang (4 套) — 近海，安静 ──
    {
        "title": "Pasir Panjang海景Condo·NUS南侧一室一厅",
        "description": "Pasir Panjang Road沿线海景Condo一室一厅，远眺新加坡海峡和裕廊岛。NUS肯特岗校区南门步行8分钟。全配高档家具，大阳台可观日落。小区有泳池/健身房/网球场。楼下公交10/30/51直达NUS和市中心。步行至Pasir Panjang Food Centre（著名海鲜美食中心）仅5分钟。适合喜欢安静海景的NUS研究生。",
        "address": "390 Pasir Panjang Road, The Foliage #07-03, Singapore 118703",
        "district": "新加坡-巴西班让",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.2840"), "longitude": Decimal("103.7755"),
        "price_monthly": Decimal("12000"), "deposit_amount": 12000,
        "area_sqm": Decimal("50"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 7, "room_number": "07-03",
        "amenities": ["WiFi", "空调", "海景阳台", "泳池", "健身房", "网球场", "家具齐全"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Pasir Panjang·NUS南门步行5分钟Studio",
        "description": "NUS肯特岗校区南门（PGP宿舍方向）步行仅5分钟，距Science Library/工学院超近。精装Studio，独立厨卫，配空调/热水器/洗衣机。全配IKEA家具。楼下公交站多线路通往全岛。周边有Sheng Siong超市和多家食阁。适合早出晚归泡实验室的NUS理工科研究生。",
        "address": "450 Pasir Panjang Road, Singapore 118793",
        "district": "新加坡-巴西班让",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.2828"), "longitude": Decimal("103.7782"),
        "price_monthly": Decimal("6500"), "deposit_amount": 6500,
        "area_sqm": Decimal("24"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 4, "room_number": "04-01",
        "amenities": ["WiFi", "空调", "近校园", "家具齐全", "独立卫浴"],
        "available_from": date(2026, 8, 5),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Pasir Panjang Hill·HDB高层两室整租（看海）",
        "description": "Pasir Panjang Hill（山坡上的HDB，视野极佳），高层两室一厅，客厅和主卧均可远眺海景。Blk属Point Block（一梯两户），极其安静。步行至NUS南门约10分钟（上坡路，当锻炼）。全空调/热水器/洗衣机。楼下咖啡店和便利店。适合两个NUS学生整租，空间宽敞舒适。",
        "address": "Blk 5 Pasir Panjang Hill, #18-02, Singapore 118805",
        "district": "新加坡-巴西班让",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.2805"), "longitude": Decimal("103.7810"),
        "price_monthly": Decimal("8800"), "deposit_amount": 8800,
        "area_sqm": Decimal("62"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 18, "room_number": "18-02",
        "amenities": ["WiFi", "空调", "海景", "高层通风", "家具齐全", "安静社区"],
        "available_from": date(2026, 8, 20),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Pasir Panjang·NUS宿舍旁合租HDB Common Room",
        "description": "Pasir Panjang Road沿线HDB，距NUS PGP宿舍区步行6分钟。Common Room出租，与两位NUS本科生室友（均为华人）合租。房间虽不大但配全套家具：单人床/书桌/衣柜/空调/台灯。屋主是一对新加坡华人老夫妇（住主卧），人非常好，偶尔会做海南鸡饭给大家吃！包水电网，最短可住3个月。",
        "address": "Blk 418 Pasir Panjang Road, #05-03, Singapore 118762",
        "district": "新加坡-巴西班让",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.2860"), "longitude": Decimal("103.7730"),
        "price_monthly": Decimal("3800"), "deposit_amount": 3800,
        "area_sqm": Decimal("10"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 5, "room_number": "05-CR",
        "amenities": ["WiFi", "空调", "包水电", "家具齐全", "华人房东", "近校园"],
        "available_from": date(2026, 8, 1),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },

    # ── Queenstown (4 套) — 成熟组屋区 ──
    {
        "title": "Queenstown MRT·高层HDB一室一厅整租（NUS校车）",
        "description": "Queenstown MRT步行3分钟，NUS校车B线15分钟/公交15分钟直达校园。高层HDB一室一厅，新装修配全新空调和厨房。步行至Queensway Shopping Centre（运动用品天堂）和IKEA Alexandra。社区成熟，图书馆/银行/邮局/诊所一应俱全。适合追求性价比的NUS学生/年轻教职工。",
        "address": "Blk 160 Mei Ling Street, #33-01, Singapore 140160",
        "district": "新加坡-女皇镇",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.2940"), "longitude": Decimal("103.8020"),
        "price_monthly": Decimal("7200"), "deposit_amount": 7200,
        "area_sqm": Decimal("36"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 33, "room_number": "33-01",
        "amenities": ["WiFi", "空调", "新装修", "近地铁", "高层通风"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Queenstown·Commonwealth两室Condo（NUS师生）",
        "description": "Queenstown/Commonwealth交界处低层Condo两室一厅。距NUS校车D线车站步行5分钟，直达Kent Ridge。小区含泳池/健身房/网球场/儿童游乐区。全屋实木地板配空调，两个卧室均朝南采光好。步行至Commonwealth MRT 5分钟，周边有多家知名本地美食（Tiong Bahru Bakery等）。适合NUS师生合租。",
        "address": "85 Commonwealth Close, Commonwealth Towers #09-05, Singapore 140085",
        "district": "新加坡-女皇镇",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3000"), "longitude": Decimal("103.8000"),
        "price_monthly": Decimal("10500"), "deposit_amount": 10500,
        "area_sqm": Decimal("60"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 9, "room_number": "09-05",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "家具齐全", "近地铁", "校车直达"],
        "available_from": date(2026, 8, 10),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Queenstown Dawson·精装Studio（NUS访问学者公寓）",
        "description": "Queenstown全新Dawson Estate高层Studio，新加坡标志性HDB建筑（Skyville @ Dawson）。配独立厨卫、空调、全套家具。社区设计获国际大奖：空中花园、社区农场、跑步道。步行至Queenstown MRT 8分钟。主卧窗外俯瞰Queenstown全景。特别适合短期访学的NUS学者/研究人员，社区安静有品质。",
        "address": "86 Dawson Road, Skyville #28-03, Singapore 141086",
        "district": "新加坡-女皇镇",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.2965"), "longitude": Decimal("103.8075"),
        "price_monthly": Decimal("8500"), "deposit_amount": 8500,
        "area_sqm": Decimal("30"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 28, "room_number": "28-03",
        "amenities": ["WiFi", "空调", "空中花园", "设计建筑", "家具齐全", "景观好"],
        "available_from": date(2026, 9, 10),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Queenstown·Stirling Road HDB合租（NUS室友已入住）",
        "description": "Stirling Road成熟社区HDB四房式，两间Common Room可选（一间朝东、一间朝西）。已有两位NUS研究生入住（一男一女，均为中国留学生）。屋主为退休教师夫妇（住主卧），非常友善，平时会帮忙打扫公共区域。客厅有大餐桌可做学习区。楼下食阁/杂货店/诊所。Queenstown MRT步行6分钟。包水电网，可煮（清淡烹饪）。",
        "address": "Blk 172 Stirling Road, #11-03, Singapore 140172",
        "district": "新加坡-女皇镇",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.2920"), "longitude": Decimal("103.8005"),
        "price_monthly": Decimal("4200"), "deposit_amount": 4200,
        "area_sqm": Decimal("11"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 11, "room_number": "11-CR",
        "amenities": ["WiFi", "空调", "包水电", "家具齐全", "可煮", "近地铁", "华人房东"],
        "available_from": date(2026, 8, 1),
        "min_stay_months": 3, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },

    # ── Dover (3 套) — NUS/SP 之间 ──
    {
        "title": "Dover MRT·NUS/Singapore Poly之间一室Condo",
        "description": "Dover MRT步行4分钟，一站到Buona Vista换NUS校车。位于NUS和Singapore Polytechnic之间的便利位置。一室一厅精装Condo，小区有泳池/健身房/BBQ台。楼下有24小时便利店和食阁。公交166路直达NUS Kent Ridge。适合NUS/SP学生，通勤极其便利。",
        "address": "28 Dover Rise, Heritage View #10-02, Singapore 138686",
        "district": "新加坡-杜佛",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3038"), "longitude": Decimal("103.7785"),
        "price_monthly": Decimal("10500"), "deposit_amount": 10500,
        "area_sqm": Decimal("48"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 10, "room_number": "10-02",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "近地铁", "家具齐全"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Dover Crescent·高层HDB两室整租（NTU/NUS双校通勤）",
        "description": "Dover Crescent高层HDB两室一厅，位于NUS和NTU之间（分别约15分钟车程）。新装修，全屋木地板配全新空调×3。高层朝南，通风极佳。Dover MRT步行6分钟。楼下公交站多线路通往全岛。周边有FairPrice超市、Dover Market & Food Centre。适合NUS和NTU各一人的合租组合。",
        "address": "Blk 19 Dover Crescent, #25-02, Singapore 130019",
        "district": "新加坡-杜佛",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3055"), "longitude": Decimal("103.7750"),
        "price_monthly": Decimal("8500"), "deposit_amount": 8500,
        "area_sqm": Decimal("60"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 25, "room_number": "25-02",
        "amenities": ["WiFi", "空调", "新装修", "高层通风", "近地铁", "近超市"],
        "available_from": date(2026, 8, 15),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Dover Parkview·三室Condo整租（NUS学生之家）",
        "description": "Dover Parkview Condo三室两卫，可住3-4人。超大客厅配L型沙发和8人餐桌，完美适合NUS学生群居。小区设施：泳池、网球场、健身房、KTV房、麻将室。步行至Dover MRT 5分钟/一站到Buona Vista商圈。楼下有24小时便利店和提款机。适合3-4位NUS好友一起整租，共享学生生活。",
        "address": "36 Dover Rise, Dover Parkview #16-01, Singapore 138688",
        "district": "新加坡-杜佛",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3045"), "longitude": Decimal("103.7800"),
        "price_monthly": Decimal("15000"), "deposit_amount": 15000,
        "area_sqm": Decimal("95"), "bedrooms": 3, "bathrooms": 2,
        "property_type": PropertyType.apartment,
        "floor": 16, "room_number": "16-01",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "网球场", "KTV", "家具齐全", "适合群居"],
        "available_from": date(2026, 9, 15),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },

    # ── West Coast (3 套) — 西海岸 ──
    {
        "title": "West Coast Park旁·NUS工学院步行海景两室Condo",
        "description": "West Coast Park正对面，NUS工学院步行10分钟。两室一厅海景Condo，阳台直面西海岸公园和大海。小区设施：泳池/健身房/网球场。楼下West Coast Plaza购物中心、Cold Storage超市。周末步行去West Coast Park野餐/骑行/放风筝。适合NUS工学院研究生/博后合租。",
        "address": "2 West Coast Walk, Blue Horizon #18-05, Singapore 127000",
        "district": "新加坡-西海岸",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3123"), "longitude": Decimal("103.7618"),
        "price_monthly": Decimal("12500"), "deposit_amount": 12500,
        "area_sqm": Decimal("70"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 18, "room_number": "18-05",
        "amenities": ["WiFi", "空调", "海景", "泳池", "健身房", "近公园", "近校园"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "West Coast Drive·海景HDB一室整租（NUS优先）",
        "description": "West Coast Drive沿线HDB一室一厅，高层海景。步行至NUS工学院约12分钟。全空调/热水器/洗衣机。楼下公交30/51/143直达NUS/Clementi/市中心。步行至West Coast Market Square（海鲜熟食中心）仅3分钟，辣椒螃蟹/黑胡椒螃蟹随时吃。适合喜欢海鲜和安静海景的NUS学生。",
        "address": "Blk 612 Clementi West Street 1, #30-01, Singapore 120612",
        "district": "新加坡-西海岸",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3150"), "longitude": Decimal("103.7590"),
        "price_monthly": Decimal("7500"), "deposit_amount": 7500,
        "area_sqm": Decimal("40"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 30, "room_number": "30-01",
        "amenities": ["WiFi", "空调", "海景", "高层通风", "近校园", "近美食中心"],
        "available_from": date(2026, 8, 10),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
    },
    {
        "title": "West Coast Drive·五房HDB Master Room（看海）",
        "description": "West Coast Drive最靠近NUS的五房式HDB，Master Room带独立阳台看海！步行到NUS工学院仅8分钟。超大主卧配King床/书桌/步入式衣柜/独立卫浴。室友为一对NUS商学院研究生情侣（住另一间Common Room）和房东老夫妇（住另一间主卧，人很好）。包水电网，可小煮（煮面/煮粥）。楼下就是公交站。",
        "address": "Blk 720 Clementi West Street 2, #22-05, Singapore 120720",
        "district": "新加坡-西海岸",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3170"), "longitude": Decimal("103.7602"),
        "price_monthly": Decimal("5500"), "deposit_amount": 5500,
        "area_sqm": Decimal("18"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.shared,
        "floor": 22, "room_number": "22-MBR",
        "amenities": ["WiFi", "空调", "海景阳台", "独立卫浴", "包水电", "近校园", "步入式衣柜"],
        "available_from": date(2026, 8, 5),
        "min_stay_months": 6, "deposit_type": DepositType.one_month,
        "service_fee_rate": 0.08,
    },

    # ── Commonwealth (3 套) — 交通枢纽 ──
    {
        "title": "Commonwealth MRT·高层一室Condo（NUS/市中心双通勤）",
        "description": "Commonwealth MRT步行2分钟，地铁绿线直达NUS（Buona Vista换校车）/市中心（20分钟到Orchard）。全新Condo一室一厅，高层安静。全配家电家具，含in-unit洗衣机。楼下有Giant超市和多家餐厅。社区配泳池/健身房/空中花园。适合在NUS上学但常去市中心的学生/年轻上班族。",
        "address": "88 Commonwealth Drive, The Crest #21-03, Singapore 140088",
        "district": "新加坡-联邦",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3020"), "longitude": Decimal("103.8015"),
        "price_monthly": Decimal("11500"), "deposit_amount": 11500,
        "area_sqm": Decimal("46"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 21, "room_number": "21-03",
        "amenities": ["WiFi", "空调", "泳池", "健身房", "近地铁", "家具齐全"],
        "available_from": date(2026, 9, 1),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Commonwealth·Tanglin Halt两室HDB整租（近NUS）",
        "description": "Commonwealth/Tanglin Halt传统HDB社区两室一厅。距NUS校车D线车站步行5分钟，直达Kent Ridge。社区以本地居民为主，安静安全。楼下Tanglin Halt Market & Food Centre是新加坡最具历史感的熟食中心之一，价格全岛最低。Commonwealth MRT步行4分钟。适合注重性价比的NUS学生。",
        "address": "Blk 48 Tanglin Halt Road, #08-03, Singapore 142048",
        "district": "新加坡-联邦",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3005"), "longitude": Decimal("103.7985"),
        "price_monthly": Decimal("7800"), "deposit_amount": 7800,
        "area_sqm": Decimal("55"), "bedrooms": 2, "bathrooms": 1,
        "property_type": PropertyType.apartment,
        "floor": 8, "room_number": "08-03",
        "amenities": ["WiFi", "空调", "平价美食", "近地铁", "校车直达", "安静社区"],
        "available_from": date(2026, 8, 20),
        "min_stay_months": 12, "deposit_type": DepositType.one_month,
    },
    {
        "title": "Commonwealth Crescent·Studio短租（NUS暑期访问）",
        "description": "Commonwealth Crescent全新精装Studio，独立厨卫，配全套家具家电。Commonwealth MRT步行6分钟/Buona Vista步行15分钟。楼下有24小时便利店和洗衣店。社区安静，以年轻专业人士和学生为主。支持灵活租期1-6个月，特别适合NUS暑期访学/研究项目/短期实习的学生。租金含网络。",
        "address": "108 Commonwealth Crescent, #03-01, Singapore 140108",
        "district": "新加坡-联邦",
        "country": "SG", "institute_id": 2,
        "latitude": Decimal("1.3035"), "longitude": Decimal("103.8030"),
        "price_monthly": Decimal("6200"), "deposit_amount": 3100,
        "area_sqm": Decimal("22"), "bedrooms": 1, "bathrooms": 1,
        "property_type": PropertyType.studio,
        "floor": 3, "room_number": "03-01",
        "amenities": ["WiFi", "空调", "短租支持", "家具齐全", "新装修"],
        "available_from": date(2026, 7, 10),
        "min_stay_months": 1, "deposit_type": DepositType.half_month,
        "min_lease_months": 1, "max_lease_months": 6,
    },
]


# ============================================================
# 种子数据写入函数
# ============================================================

async def seed_properties(dry_run: bool = False, clear_existing: bool = False):
    """插入 UCLA & NUS 差异化房源种子数据"""
    async with async_session_maker() as session:
        # ── 获取可用房东 ──
        result = await session.execute(
            select(User).where(User.role == "landlord").limit(5)
        )
        landlords = result.scalars().all()

        if not landlords:
            print("[ERROR] 没有找到房东账号，请先创建房东用户！")
            return

        landlord_ids = [l.id for l in landlords]
        print(f"找到 {len(landlords)} 个房东: {[(l.id, l.username, l.role) for l in landlords]}")
        print(f"准备处理 {len(SEED_PROPERTIES)} 条房源数据\n")

        # ── 可选：清除旧数据 ──
        if clear_existing:
            ucla_count = 0
            nus_count = 0
            for pdata in SEED_PROPERTIES:
                inst_id = pdata["institute_id"]
                # 收集受影响的institute
                pass
            # 删除 institute_id 为 1 或 2 的房源
            from sqlalchemy import delete
            result1 = await session.execute(
                delete(Property).where(Property.institute_id == 1)
            )
            result2 = await session.execute(
                delete(Property).where(Property.institute_id == 2)
            )
            ucla_count = result1.rowcount
            nus_count = result2.rowcount
            print(f"[CLEAR] 已删除 UCLA {ucla_count} 套 + NUS {nus_count} 套旧房源\n")
            await session.flush()

        if dry_run:
            print("=== DRY RUN MODE ===\n")
            for i, p in enumerate(SEED_PROPERTIES):
                inst = "UCLA" if p["institute_id"] == 1 else "NUS"
                print(f"  [{i+1:02d}] [{inst}] {p['title'][:50]}")
                print(f"        地址: {p['address'][:55]}")
                print(f"        区域: {p['district']}  |  CNY{p['price_monthly']}/月  |  "
                      f"{p['bedrooms']}室{p['bathrooms']}卫  |  {p['property_type'].value}")
                print(f"        坐标: ({p['latitude']}, {p['longitude']})")
                ams = p.get("amenities", [])
                if ams:
                    print(f"        设施: {', '.join(ams)}")
                print()
            ucla_count = sum(1 for p in SEED_PROPERTIES if p["institute_id"] == 1)
            nus_count = sum(1 for p in SEED_PROPERTIES if p["institute_id"] == 2)
            print(f"[DRY RUN] 将插入 UCLA {ucla_count} 套 + NUS {nus_count} 套 = {len(SEED_PROPERTIES)} 套房源")
            return

        # ── 正式插入 ──
        created = 0
        ucla_created = 0
        nus_created = 0
        for i, pdata in enumerate(SEED_PROPERTIES):
            landlord_id = landlord_ids[i % len(landlord_ids)]
            # 提取 amenities 等特殊字段（不在 Property(**kwargs) 直接展开）
            extra = {}
            for key in list(pdata.keys()):
                if key not in {
                    "title", "description", "address", "district", "country",
                    "latitude", "longitude", "price_monthly", "deposit_amount",
                    "area_sqm", "bedrooms", "bathrooms", "property_type",
                    "institute_id", "floor", "room_number", "amenities",
                    "available_from", "min_stay_months", "deposit_type",
                    "service_fee_rate", "min_lease_months", "max_lease_months",
                }:
                    extra[key] = pdata.pop(key)

            # 构建 amenity 等额外字段
            amenities = pdata.pop("amenities", None)
            available_from = pdata.pop("available_from", None)
            min_stay = pdata.pop("min_stay_months", 3)
            deposit_type = pdata.pop("deposit_type", None)
            service_fee = pdata.pop("service_fee_rate", 0.10)
            min_lease = pdata.pop("min_lease_months", 12)
            max_lease = pdata.pop("max_lease_months", 60)
            floor = pdata.pop("floor", None)
            room = pdata.pop("room_number", None)

            prop = Property(
                landlord_id=landlord_id,
                status=PropertyStatus.available,
                rent_type=RentType.monthly,
                amenities=amenities,
                available_from=available_from,
                min_stay_months=min_stay,
                deposit_type=deposit_type,
                service_fee_rate=service_fee,
                min_lease_months=min_lease,
                max_lease_months=max_lease,
                floor=floor,
                room_number=room,
                **pdata,
            )
            session.add(prop)
            created += 1
            if pdata["institute_id"] == 1:
                ucla_created += 1
            else:
                nus_created += 1
            inst_label = "UCLA" if pdata["institute_id"] == 1 else "NUS"
            print(f"  [{created:02d}] [{inst_label}] OK {pdata['title'][:45]}...")

        await session.commit()
        print(f"\n[DONE] 成功插入 UCLA {ucla_created} 套 + NUS {nus_created} 套 = {created} 套房源！")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    clear = "--clear-existing" in sys.argv
    asyncio.run(seed_properties(dry_run=dry, clear_existing=clear))

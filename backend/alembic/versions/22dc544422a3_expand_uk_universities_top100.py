"""expand_uk_universities_top100

Revision ID: 22dc544422a3
Revises: 7ac813cadcec
Create Date: 2026-08-12 00:54:09.369755

将英国大学扩充至 QS 排名前 100，覆盖全英主要城市。
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = '22dc544422a3'
down_revision: Union[str, None] = '7ac813cadcec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── QS 2025 英国前 100 大学数据 ──
# 格式: (name, name_cn, abbreviation, aliases, city, country, lat, lng, is_hot)
# aliases 用分号分隔，SQL 中转为数组

UK_UNIVERSITIES = [
    # ═══ 伦敦地区 (已有部分，新增 aliases 更新) ═══
    ("Imperial College London", "帝国理工学院", "Imperial", "帝国理工", "London", "GB", 51.4988, -0.1749, True),
    ("University College London", "伦敦大学学院", "UCL", "UCL", "London", "GB", 51.5246, -0.1336, True),
    ("King's College London", "伦敦国王学院", "KCL", "KCL;国王学院", "London", "GB", 51.5113, -0.1165, True),
    ("London School of Economics and Political Science", "伦敦政治经济学院", "LSE", "LSE;伦敦政经", "London", "GB", 51.5144, -0.1167, True),
    ("Queen Mary University of London", "伦敦玛丽女王大学", "QMUL", "QMUL;玛丽女王", "London", "GB", 51.5241, -0.0403, False),
    ("Royal Holloway, University of London", "伦敦大学皇家霍洛威学院", "RHUL", "RHUL;皇家霍洛威", "Egham", "GB", 51.4249, -0.5653, False),
    ("SOAS University of London", "伦敦大学亚非学院", "SOAS", "SOAS;亚非学院", "London", "GB", 51.5224, -0.1290, False),
    ("Birkbeck, University of London", "伦敦大学伯贝克学院", "Birkbeck", "Birkbeck;伯贝克", "London", "GB", 51.5219, -0.1303, False),
    ("Goldsmiths, University of London", "伦敦大学金史密斯学院", "Goldsmiths", "Goldsmiths;金史密斯", "London", "GB", 51.4744, -0.0356, False),
    ("City, University of London", "伦敦大学城市学院", "City", "City;城市学院", "London", "GB", 51.5278, -0.1024, False),
    ("University of the Arts London", "伦敦艺术大学", "UAL", "UAL;伦艺", "London", "GB", 51.5186, -0.1347, False),
    ("University of Westminster", "威斯敏斯特大学", "Westminster", "Westminster;威敏", "London", "GB", 51.5172, -0.1420, False),
    ("Brunel University London", "布鲁内尔大学", "Brunel", "Brunel;布鲁内尔", "London", "GB", 51.5329, -0.4726, False),
    ("University of Greenwich", "格林威治大学", "Greenwich", "Greenwich;格林威治", "London", "GB", 51.4827, -0.0058, False),
    ("Middlesex University", "密德萨斯大学", "Middlesex", "Middlesex;密德萨斯", "London", "GB", 51.5895, -0.2282, False),
    ("University of East London", "东伦敦大学", "UEL", "UEL;东伦敦", "London", "GB", 51.5082, 0.0611, False),
    ("London South Bank University", "伦敦南岸大学", "LSBU", "LSBU;南岸大学", "London", "GB", 51.4982, -0.1018, False),
    ("University of Roehampton", "罗汉普顿大学", "Roehampton", "Roehampton;罗汉普顿", "London", "GB", 51.4564, -0.2431, False),
    ("Kingston University", "金斯顿大学", "Kingston", "Kingston;金斯顿", "London", "GB", 51.4304, -0.3028, False),
    ("University of West London", "西伦敦大学", "UWL", "UWL;西伦敦", "London", "GB", 51.5074, -0.3043, False),
    ("Royal College of Art", "皇家艺术学院", "RCA", "RCA;皇家艺术", "London", "GB", 51.5009, -0.1775, False),
    ("Royal Academy of Music", "皇家音乐学院", "RAM", "RAM;皇家音乐", "London", "GB", 51.5235, -0.1520, False),
    ("Royal College of Music", "皇家音乐学院(RCM)", "RCM", "RCM", "London", "GB", 51.4995, -0.1773, False),
    ("Trinity Laban Conservatoire of Music and Dance", "圣三一拉邦音乐舞蹈学院", "TrinityLaban", "TrinityLaban;圣三一拉邦", "London", "GB", 51.4805, -0.0094, False),
    ("Guildhall School of Music and Drama", "市政厅音乐戏剧学院", "Guildhall", "Guildhall;市政厅", "London", "GB", 51.5197, -0.0933, False),
    ("Central Saint Martins", "中央圣马丁艺术设计学院", "CSM", "CSM;中央圣马丁;圣马丁", "London", "GB", 51.5354, -0.1246, False),
    ("London College of Fashion", "伦敦时装学院", "LCF", "LCF;伦敦时装", "London", "GB", 51.5176, -0.1387, False),
    ("London Metropolitan University", "伦敦都市大学", "LondonMet", "LondonMet;伦敦都市", "London", "GB", 51.5513, -0.1109, False),
    ("St George's, University of London", "伦敦大学圣乔治学院", "StGeorge", "StGeorge;圣乔治", "London", "GB", 51.4271, -0.1741, False),

    # ═══ 牛津 / 剑桥 ═══
    ("University of Oxford", "牛津大学", "Oxford", "牛津;Oxon", "Oxford", "GB", 51.7548, -1.2544, True),
    ("University of Cambridge", "剑桥大学", "Cambridge", "剑桥;Camb", "Cambridge", "GB", 52.2053, 0.1218, True),
    ("Oxford Brookes University", "牛津布鲁克斯大学", "OxfordBrookes", "牛津布鲁克斯;OBU", "Oxford", "GB", 51.7520, -1.2221, False),
    ("Anglia Ruskin University", "安格利亚鲁斯金大学", "ARU", "ARU;安格利亚鲁斯金", "Cambridge", "GB", 52.2039, 0.1350, False),

    # ═══ 苏格兰 ═══
    ("University of Edinburgh", "爱丁堡大学", "Edinburgh", "爱大;Edin", "Edinburgh", "GB", 55.9445, -3.1879, True),
    ("University of Glasgow", "格拉斯哥大学", "Glasgow", "格大;Glas", "Glasgow", "GB", 55.8721, -4.2888, True),
    ("University of St Andrews", "圣安德鲁斯大学", "StAndrews", "圣安;StA", "St Andrews", "GB", 56.3398, -2.7967, True),
    ("University of Strathclyde", "思克莱德大学", "Strathclyde", "Strath;思克莱德", "Glasgow", "GB", 55.8622, -4.2430, False),
    ("Heriot-Watt University", "赫瑞瓦特大学", "HeriotWatt", "赫瑞瓦特;HW", "Edinburgh", "GB", 55.9097, -3.3204, False),
    ("University of Dundee", "邓迪大学", "Dundee", "邓迪;Dund", "Dundee", "GB", 56.4571, -2.9813, False),
    ("University of Aberdeen", "阿伯丁大学", "Aberdeen", "阿伯丁;Abd", "Aberdeen", "GB", 57.1646, -2.1010, False),
    ("University of Stirling", "斯特灵大学", "Stirling", "斯特灵;Stir", "Stirling", "GB", 56.1450, -3.9203, False),
    ("Edinburgh Napier University", "爱丁堡龙比亚大学", "Napier", "龙比亚;Napier", "Edinburgh", "GB", 55.9333, -3.2133, False),
    ("Glasgow Caledonian University", "格拉斯哥卡利多尼亚大学", "GCU", "GCU;卡利多尼亚", "Glasgow", "GB", 55.8663, -4.2495, False),
    ("University of the West of Scotland", "西苏格兰大学", "UWS", "UWS;西苏格兰", "Paisley", "GB", 55.8440, -4.4326, False),
    ("Robert Gordon University", "罗伯特戈登大学", "RGU", "RGU;罗伯特戈登", "Aberdeen", "GB", 57.1475, -2.1013, False),
    ("Abertay University", "阿伯泰大学", "Abertay", "阿伯泰;Abertay", "Dundee", "GB", 56.4635, -2.9732, False),
    ("Queen Margaret University", "玛格丽特女王大学", "QMU", "QMU;玛格丽特女王", "Edinburgh", "GB", 55.9312, -3.0722, False),

    # ═══ 英格兰北部 ═══
    ("University of Manchester", "曼彻斯特大学", "Manchester", "曼大;UoM", "Manchester", "GB", 53.4662, -2.2334, True),
    ("Manchester Metropolitan University", "曼彻斯特城市大学", "MMU", "MMU;曼城大", "Manchester", "GB", 53.4706, -2.2398, False),
    ("University of Salford", "索尔福德大学", "Salford", "索尔福德;Salford", "Manchester", "GB", 53.4871, -2.2736, False),
    ("University of Leeds", "利兹大学", "Leeds", "利大;Leeds", "Leeds", "GB", 53.8072, -1.5542, True),
    ("Leeds Beckett University", "利兹贝克特大学", "LeedsBeckett", "利兹贝克特;LBU", "Leeds", "GB", 53.8040, -1.5484, False),
    ("University of Sheffield", "谢菲尔德大学", "Sheffield", "谢大;Shef", "Sheffield", "GB", 53.3808, -1.4885, True),
    ("Sheffield Hallam University", "谢菲尔德哈勒姆大学", "SHU", "SHU;哈勒姆", "Sheffield", "GB", 53.3782, -1.4652, False),
    ("University of York", "约克大学", "York", "约大;York", "York", "GB", 53.9474, -1.0522, True),
    ("York St John University", "约克圣约翰大学", "YSJ", "YSJ;约克圣约翰", "York", "GB", 53.9648, -1.0804, False),
    ("Newcastle University", "纽卡斯尔大学", "Newcastle", "纽大;NCL", "Newcastle", "GB", 54.9790, -1.6147, True),
    ("Northumbria University", "诺森比亚大学", "Northumbria", "诺森比亚;Northumbria", "Newcastle", "GB", 54.9764, -1.6080, False),
    ("Durham University", "杜伦大学", "Durham", "杜伦;Dur", "Durham", "GB", 54.7681, -1.5720, True),
    ("University of Hull", "赫尔大学", "Hull", "赫尔;Hull", "Hull", "GB", 53.7701, -0.3672, False),
    ("University of Huddersfield", "哈德斯菲尔德大学", "Huddersfield", "哈德斯菲尔德;Hud", "Huddersfield", "GB", 53.6437, -1.7791, False),
    ("University of Bradford", "布拉德福德大学", "Bradford", "布拉德福德;Brad", "Bradford", "GB", 53.7912, -1.7674, False),
    ("Teesside University", "提赛德大学", "Teesside", "提赛德;Teesside", "Middlesbrough", "GB", 54.5730, -1.2359, False),
    ("University of Sunderland", "桑德兰大学", "Sunderland", "桑德兰;Sun", "Sunderland", "GB", 54.9059, -1.3753, False),

    # ═══ 英格兰中部 (Midlands) ═══
    ("University of Birmingham", "伯明翰大学", "Birmingham", "伯大;Bham", "Birmingham", "GB", 52.4508, -1.9305, True),
    ("Aston University", "阿斯顿大学", "Aston", "阿斯顿;Aston", "Birmingham", "GB", 52.4867, -1.8885, False),
    ("Birmingham City University", "伯明翰城市大学", "BCU", "BCU;伯城大", "Birmingham", "GB", 52.4822, -1.8948, False),
    ("University of Warwick", "华威大学", "Warwick", "华威;Warw", "Coventry", "GB", 52.3800, -1.5619, True),
    ("Coventry University", "考文垂大学", "Coventry", "考文垂;Cov", "Coventry", "GB", 52.4081, -1.5057, False),
    ("University of Nottingham", "诺丁汉大学", "Nottingham", "诺大;UoN", "Nottingham", "GB", 52.9386, -1.1967, True),
    ("Nottingham Trent University", "诺丁汉特伦特大学", "NTU", "NTU;特伦特", "Nottingham", "GB", 52.9562, -1.1522, False),
    ("University of Leicester", "莱斯特大学", "Leicester", "莱大;Leic", "Leicester", "GB", 52.6219, -1.1246, False),
    ("De Montfort University", "德蒙福特大学", "DMU", "DMU;德蒙福特", "Leicester", "GB", 52.6293, -1.1392, False),
    ("Loughborough University", "拉夫堡大学", "Loughborough", "拉夫堡;Lboro", "Loughborough", "GB", 52.7687, -1.2245, True),
    ("Keele University", "基尔大学", "Keele", "基尔;Keele", "Newcastle-under-Lyme", "GB", 53.0034, -2.2710, False),
    ("Staffordshire University", "斯塔福德郡大学", "Staffs", "斯塔福德郡;Staffs", "Stoke-on-Trent", "GB", 53.0089, -2.1786, False),
    ("University of Derby", "德比大学", "Derby", "德比;Derby", "Derby", "GB", 52.9379, -1.4976, False),
    ("University of Wolverhampton", "伍尔弗汉普顿大学", "Wolves", "伍尔弗汉普顿;Wolves", "Wolverhampton", "GB", 52.5870, -2.1280, False),
    ("University of Northampton", "北安普顿大学", "Northampton", "北安普顿;Northampton", "Northampton", "GB", 52.2518, -0.8928, False),
    ("University of Lincoln", "林肯大学", "Lincoln", "林肯;Linc", "Lincoln", "GB", 53.2284, -0.5480, False),

    # ═══ 英格兰西北 ═══
    ("University of Liverpool", "利物浦大学", "Liverpool", "利大;Liv", "Liverpool", "GB", 53.4060, -2.9668, True),
    ("Liverpool John Moores University", "利物浦约翰摩尔斯大学", "LJMU", "LJMU;约翰摩尔斯", "Liverpool", "GB", 53.4032, -2.9703, False),
    ("Liverpool Hope University", "利物浦霍普大学", "LiverpoolHope", "利物浦霍普;Hope", "Liverpool", "GB", 53.3912, -2.8950, False),
    ("Lancaster University", "兰卡斯特大学", "Lancaster", "兰卡;Lancs", "Lancaster", "GB", 54.0105, -2.7864, True),
    ("University of Central Lancashire", "中央兰开夏大学", "UCLan", "UCLan;中央兰开夏", "Preston", "GB", 53.7632, -2.7040, False),
    ("Edge Hill University", "边山大学", "EdgeHill", "边山;EdgeHill", "Ormskirk", "GB", 53.5570, -2.8717, False),
    ("University of Chester", "切斯特大学", "Chester", "切斯特;Chester", "Chester", "GB", 53.1989, -2.8961, False),
    ("University of Cumbria", "坎布里亚大学", "Cumbria", "坎布里亚;Cumbria", "Carlisle", "GB", 54.8925, -2.9320, False),

    # ═══ 英格兰西南 ═══
    ("University of Bristol", "布里斯托大学", "Bristol", "布大;Bris", "Bristol", "GB", 51.4578, -2.6027, True),
    ("University of the West of England", "西英格兰大学", "UWE", "UWE;西英格兰", "Bristol", "GB", 51.5002, -2.5474, False),
    ("University of Bath", "巴斯大学", "Bath", "巴斯;Bath", "Bath", "GB", 51.3781, -2.3270, True),
    ("Bath Spa University", "巴斯斯巴大学", "BathSpa", "巴斯斯巴;BathSpa", "Bath", "GB", 51.3744, -2.3499, False),
    ("University of Exeter", "埃克塞特大学", "Exeter", "埃克塞特;Exe", "Exeter", "GB", 50.7362, -3.5343, True),
    ("University of Plymouth", "普利茅斯大学", "Plymouth", "普利茅斯;Plym", "Plymouth", "GB", 50.3755, -4.1392, False),
    ("Bournemouth University", "伯恩茅斯大学", "Bournemouth", "伯恩茅斯;BU", "Bournemouth", "GB", 50.7420, -1.8974, False),
    ("Arts University Bournemouth", "伯恩茅斯艺术大学", "AUB", "AUB;伯恩茅斯艺术", "Bournemouth", "GB", 50.7414, -1.8975, False),
    ("University of Gloucestershire", "格洛斯特郡大学", "Glos", "格洛斯特郡;Glos", "Cheltenham", "GB", 51.8872, -2.0886, False),
    ("Falmouth University", "法尔茅斯大学", "Falmouth", "法尔茅斯;Falmouth", "Falmouth", "GB", 50.1505, -5.0682, False),
    ("Royal Agricultural University", "皇家农业大学", "RAU", "RAU;皇家农业", "Cirencester", "GB", 51.7100, -1.9948, False),
    ("Hartpury University", "哈特伯瑞大学", "Hartpury", "哈特伯瑞;Hartpury", "Gloucester", "GB", 51.9084, -2.3008, False),

    # ═══ 英格兰东南 ═══
    ("University of Southampton", "南安普顿大学", "Southampton", "南安;Soton", "Southampton", "GB", 50.9343, -1.3957, True),
    ("Solent University", "索伦特大学", "Solent", "索伦特;Solent", "Southampton", "GB", 50.9080, -1.4006, False),
    ("University of Portsmouth", "朴茨茅斯大学", "Portsmouth", "朴茨茅斯;Port", "Portsmouth", "GB", 50.7951, -1.0928, False),
    ("University of Sussex", "萨塞克斯大学", "Sussex", "萨塞克斯;Sussex", "Brighton", "GB", 50.8654, -0.0877, True),
    ("University of Brighton", "布莱顿大学", "Brighton", "布莱顿;Brighton", "Brighton", "GB", 50.8425, -0.1192, False),
    ("University of Reading", "雷丁大学", "Reading", "雷丁;Reading", "Reading", "GB", 51.4414, -0.9416, False),
    ("University of Surrey", "萨里大学", "Surrey", "萨里;Surrey", "Guildford", "GB", 51.2428, -0.5904, False),
    ("University of Kent", "肯特大学", "Kent", "肯特;Kent", "Canterbury", "GB", 51.2970, 1.0682, False),
    ("Canterbury Christ Church University", "坎特伯雷基督教会大学", "CCCU", "CCCU;基督教会", "Canterbury", "GB", 51.2799, 1.0844, False),
    ("University for the Creative Arts", "创意艺术大学", "UCA", "UCA;创意艺术", "Farnham", "GB", 51.2137, -0.8016, False),
    ("University of Chichester", "奇切斯特大学", "Chichester", "奇切斯特;Chich", "Chichester", "GB", 50.8432, -0.7742, False),
    ("University of Winchester", "温切斯特大学", "Winchester", "温切斯特;Winc", "Winchester", "GB", 51.0620, -1.3177, False),
    ("Buckinghamshire New University", "白金汉郡新大学", "BNU", "BNU;白金汉郡", "High Wycombe", "GB", 51.6291, -0.7490, False),
    ("University of Buckingham", "白金汉大学", "Buckingham", "白金汉;Buck", "Buckingham", "GB", 52.0007, -0.9873, False),

    # ═══ 英格兰东部 ═══
    ("University of East Anglia", "东英吉利大学", "UEA", "UEA;东英吉利", "Norwich", "GB", 52.6222, 1.2413, False),
    ("University of Essex", "埃塞克斯大学", "Essex", "埃塞克斯;Essex", "Colchester", "GB", 51.8766, 0.9469, False),
    ("University of Hertfordshire", "赫特福德大学", "Herts", "赫特福德;Herts", "Hatfield", "GB", 51.7535, -0.2429, False),
    ("University of Bedfordshire", "贝德福德郡大学", "Beds", "贝德福德郡;Beds", "Luton", "GB", 51.8788, -0.4167, False),
    ("Cranfield University", "克兰菲尔德大学", "Cranfield", "克兰菲尔德;Cranfield", "Cranfield", "GB", 52.0742, -0.6288, False),
    ("University of Suffolk", "萨福克大学", "Suffolk", "萨福克;Suffolk", "Ipswich", "GB", 52.0526, 1.1617, False),
    ("Norwich University of the Arts", "诺里奇艺术大学", "NUA", "NUA;诺里奇艺术", "Norwich", "GB", 52.6305, 1.2964, False),

    # ═══ 威尔士 ═══
    ("Cardiff University", "卡迪夫大学", "Cardiff", "卡大;Cardiff", "Cardiff", "GB", 51.4875, -3.1790, True),
    ("Cardiff Metropolitan University", "卡迪夫城市大学", "CardiffMet", "卡迪夫城市;CardiffMet", "Cardiff", "GB", 51.4957, -3.1735, False),
    ("Swansea University", "斯旺西大学", "Swansea", "斯旺西;Swan", "Swansea", "GB", 51.6093, -3.9803, False),
    ("University of South Wales", "南威尔士大学", "USW", "USW;南威尔士", "Pontypridd", "GB", 51.5895, -3.3221, False),
    ("Aberystwyth University", "阿伯里斯特威斯大学", "Aberystwyth", "阿伯里斯特威斯;Aber", "Aberystwyth", "GB", 52.4153, -4.0647, False),
    ("Bangor University", "班戈大学", "Bangor", "班戈;Bangor", "Bangor", "GB", 53.2280, -4.1293, False),
    ("University of Wales Trinity Saint David", "威尔士三一圣大卫大学", "UWTSD", "UWTSD;三一圣大卫", "Carmarthen", "GB", 51.8565, -4.3103, False),
    ("Wrexham University", "雷克瑟姆大学", "Wrexham", "雷克瑟姆;Wrexham", "Wrexham", "GB", 53.0517, -3.0069, False),

    # ═══ 北爱尔兰 ═══
    ("Queen's University Belfast", "贝尔法斯特女王大学", "QUB", "QUB;女王大学;贝法女王", "Belfast", "GB", 54.5844, -5.9352, True),
    ("Ulster University", "阿尔斯特大学", "Ulster", "阿尔斯特;Ulster", "Coleraine", "GB", 55.1473, -6.6742, False),
]


def upgrade() -> None:
    conn = op.get_bind()

    # 删除现有英国大学
    conn.execute(text("DELETE FROM universities WHERE country = 'GB'"))

    # 插入新数据
    for name, name_cn, abbr, aliases_str, city, country, lat, lng, is_hot in UK_UNIVERSITIES:
        aliases_list = [a.strip() for a in aliases_str.split(";") if a.strip()] if aliases_str else None
        conn.execute(
            text(
                """INSERT INTO universities
                   (name, name_cn, abbreviation, aliases, city, country, latitude, longitude, is_active, is_hot)
                   VALUES (:name, :name_cn, :abbr, :aliases, :city, :country, :lat, :lng, true, :is_hot)"""
            ),
            {
                "name": name,
                "name_cn": name_cn,
                "abbr": abbr,
                "aliases": aliases_list,
                "city": city,
                "country": country,
                "lat": lat,
                "lng": lng,
                "is_hot": is_hot,
            },
        )


def downgrade() -> None:
    """回滚：恢复原有的精简版英国大学列表"""
    conn = op.get_bind()
    conn.execute(text("DELETE FROM universities WHERE country = 'GB'"))
    # 只恢复原有伦敦大学，手动插入
    OLD_UK = [
        ("University College London", "伦敦大学学院", "UCL", None, "London", 51.5246, -0.1336),
        ("Imperial College London", "帝国理工学院", "Imperial", None, "London", 51.4988, -0.1749),
        ("London School of Economics and Political Science", "伦敦政治经济学院", "LSE", None, "London", 51.5144, -0.1167),
        ("King's College London", "伦敦国王学院", "KCL", None, "London", 51.5113, -0.1165),
        ("Queen Mary University of London", "伦敦玛丽女王大学", "QMUL", None, "London", 51.5241, -0.0403),
        ("University of the Arts London", "伦敦艺术大学", "UAL", None, "London", 51.5186, -0.1347),
        ("University of Westminster", "威斯敏斯特大学", "Westminster", None, "London", 51.5172, -0.1420),
        ("City, University of London", "伦敦大学城市学院", "City", None, "London", 51.5278, -0.1024),
        ("Birkbeck, University of London", "伦敦大学伯贝克学院", "Birkbeck", None, "London", 51.5219, -0.1303),
        ("Goldsmiths, University of London", "伦敦大学金史密斯学院", "Goldsmiths", None, "London", 51.4744, -0.0356),
        ("Royal Holloway, University of London", "伦敦大学皇家霍洛威学院", "RHUL", None, "Egham", 51.4249, -0.5653),
        ("SOAS University of London", "伦敦大学亚非学院", "SOAS", None, "London", 51.5224, -0.1290),
        ("Brunel University London", "布鲁内尔大学", "Brunel", None, "London", 51.5329, -0.4726),
        ("University of Greenwich", "格林威治大学", "Greenwich", None, "London", 51.4827, -0.0058),
        ("Middlesex University", "密德萨斯大学", "Middlesex", None, "London", 51.5895, -0.2282),
        ("University of East London", "东伦敦大学", "UEL", None, "London", 51.5082, 0.0611),
        ("London South Bank University", "伦敦南岸大学", "LSBU", None, "London", 51.4982, -0.1018),
        ("University of Roehampton", "罗汉普顿大学", "Roehampton", None, "London", 51.4564, -0.2431),
        ("Kingston University", "金斯顿大学", "Kingston", None, "London", 51.4304, -0.3028),
        ("University of West London", "西伦敦大学", "UWL", None, "London", 51.5074, -0.3043),
        ("Royal College of Art", "皇家艺术学院", "RCA", None, "London", 51.5009, -0.1775),
        ("Royal Academy of Music", "皇家音乐学院", "RAM", None, "London", 51.5235, -0.1520),
        ("Royal College of Music", "皇家音乐学院(RCM)", "RCM", None, "London", 51.4995, -0.1773),
        ("Trinity Laban Conservatoire of Music and Dance", "圣三一拉邦音乐舞蹈学院", "TrinityLaban", None, "London", 51.4805, -0.0094),
        ("Guildhall School of Music and Drama", "市政厅音乐戏剧学院", "Guildhall", None, "London", 51.5197, -0.0933),
        ("Central Saint Martins", "中央圣马丁艺术设计学院", "CSM", None, "London", 51.5354, -0.1246),
        ("London College of Fashion", "伦敦时装学院", "LCF", None, "London", 51.5176, -0.1387),
        ("London Metropolitan University", "伦敦都市大学", "LondonMet", None, "London", 51.5513, -0.1109),
        ("St George's, University of London", "伦敦大学圣乔治学院", "StGeorge", None, "London", 51.4271, -0.1741),
    ]
    for name, name_cn, abbr, aliases, city, lat, lng in OLD_UK:
        conn.execute(
            text(
                """INSERT INTO universities
                   (name, name_cn, abbreviation, aliases, city, country, latitude, longitude, is_active, is_hot)
                   VALUES (:name, :name_cn, :abbr, :aliases, :city, 'GB', :lat, :lng, true, false)"""
            ),
            {"name": name, "name_cn": name_cn, "abbr": abbr, "aliases": aliases, "city": city, "lat": lat, "lng": lng},
        )

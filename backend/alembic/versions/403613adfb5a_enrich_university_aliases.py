"""enrich_university_aliases

Revision ID: 403613adfb5a
Revises: 22dc544422a3
Create Date: 2026-08-12 01:03:06.856823

为所有英国 + 新加坡大学扩充别名（每所 3-6 个），覆盖常见简称/英文名/地名别名。
"""

from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = '403613adfb5a'
down_revision: Union[str, None] = '22dc544422a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# key = name (英文全名), value = [别名1, 别名2, ...]
ALIASES: dict[str, list[str]] = {
    # ═══ 伦敦地区 ═══
    "Imperial College London": [
        "帝国理工", "帝国理工學院", "ICL", "IC", "伦敦帝国学院",
        "Imperial College", "帝国学院",
    ],
    "University College London": [
        "UCL", "伦敦大学学院", "伦敦大学", "伦大学院", "UCLondon",
    ],
    "King's College London": [
        "国王学院", "KCL", "伦敦国王", "King's", "Kings College",
        "Kings College London", "伦敦国王大学",
    ],
    "London School of Economics and Political Science": [
        "伦敦政经", "LSE", "伦敦政治经济", "政经学院", "伦敦政经学院",
    ],
    "Queen Mary University of London": [
        "玛丽女王", "QMUL", "QM", "Queen Mary", "伦敦玛丽女王",
        "伦敦皇后玛丽", "皇后玛丽",
    ],
    "Royal Holloway, University of London": [
        "皇家霍洛威", "RHUL", "RH", "Holloway", "霍洛威学院",
        "皇家霍洛威学院",
    ],
    "SOAS University of London": [
        "亚非学院", "SOAS", "伦敦亚非", "亚非研究",
    ],
    "Birkbeck, University of London": [
        "伯贝克", "Birkbeck", "BBK", "伦敦伯贝克",
    ],
    "Goldsmiths, University of London": [
        "金史密斯", "Goldsmiths", "金匠", "金匠学院", "伦敦金史密斯",
    ],
    "City, University of London": [
        "城市学院", "City University", "CUL", "伦敦城市大学",
        "City Uni", "伦敦城市",
    ],
    "University of the Arts London": [
        "伦艺", "UAL", "伦敦艺术", "伦敦艺术大学", "Arts London",
    ],
    "University of Westminster": [
        "威敏", "Westminster", "威敏斯特", "西敏寺大学", "威敏大学",
    ],
    "Brunel University London": [
        "Brunel", "布鲁内尔", "布鲁内耳", "布鲁乃尔",
    ],
    "University of Greenwich": [
        "Greenwich", "格林威治", "格林尼治", "格林威治大学",
    ],
    "Middlesex University": [
        "Middlesex", "密德萨斯", "密德萨斯大学", "米德尔塞克斯",
    ],
    "University of East London": [
        "东伦敦", "UEL", "East London", "东伦敦大学",
    ],
    "London South Bank University": [
        "南岸大学", "LSBU", "South Bank", "伦敦南岸", "南岸",
    ],
    "University of Roehampton": [
        "Roehampton", "罗汉普顿", "罗汉普敦",
    ],
    "Kingston University": [
        "Kingston", "金斯顿", "金斯敦", "京士顿",
    ],
    "University of West London": [
        "西伦敦", "UWL", "West London", "西伦敦大学",
    ],
    "Royal College of Art": [
        "皇家艺术", "RCA", "皇家艺术学院", "皇家美院",
    ],
    "Royal Academy of Music": [
        "皇家音乐", "RAM", "皇家音乐学院", "英皇音乐学院",
    ],
    "Royal College of Music": [
        "皇家音乐(RCM)", "RCM", "皇家音乐学院RCM", "英皇音乐RCM",
    ],
    "Trinity Laban Conservatoire of Music and Dance": [
        "圣三一拉邦", "TrinityLaban", "圣三一", "三一拉邦",
        "圣三一音乐舞蹈学院", "Trinity Laban",
    ],
    "Guildhall School of Music and Drama": [
        "市政厅", "Guildhall", "市政厅音乐戏剧", "Guildhall School",
    ],
    "Central Saint Martins": [
        "中央圣马丁", "圣马丁", "CSM", "中央圣马丁学院", "圣马丁学院",
    ],
    "London College of Fashion": [
        "伦敦时装", "LCF", "伦敦时装学院", "时装学院",
    ],
    "London Metropolitan University": [
        "伦敦都市", "LondonMet", "LMU", "都市大学", "伦敦城市大学",
    ],
    "St George's, University of London": [
        "圣乔治", "StGeorge", "SGUL", "伦敦圣乔治", "圣乔治医学院",
    ],

    # ═══ 牛津 / 剑桥 ═══
    "University of Oxford": [
        "牛津", "Oxford", "Oxon", "牛津大学", "Oxf",
    ],
    "University of Cambridge": [
        "剑桥", "Cambridge", "Camb", "剑桥大学", "Cam",
    ],
    "Oxford Brookes University": [
        "牛津布鲁克斯", "OBU", "Brookes", "牛津布大", "布鲁克斯大学",
    ],
    "Anglia Ruskin University": [
        "安格利亚鲁斯金", "ARU", "Anglia Ruskin", "安格利亚",
        "鲁斯金大学",
    ],

    # ═══ 苏格兰 ═══
    "University of Edinburgh": [
        "爱大", "爱丁堡", "Edinburgh", "Edin", "爱丁堡大学",
    ],
    "University of Glasgow": [
        "格大", "格拉斯哥", "Glasgow", "Glas", "格拉", "格拉斯哥大学",
    ],
    "University of St Andrews": [
        "圣安", "圣安德鲁斯", "StAndrews", "StA", "圣安大",
        "圣安德鲁斯大学",
    ],
    "University of Strathclyde": [
        "Strath", "Strathclyde", "思克莱德", "斯克莱德", "思克莱德大学",
    ],
    "Heriot-Watt University": [
        "赫瑞瓦特", "HW", "HeriotWatt", "赫瑞瓦特大学",
        "赫里奥特瓦特", "瓦特大学",
    ],
    "University of Dundee": [
        "邓迪", "Dundee", "Dund", "邓迪大学",
    ],
    "University of Aberdeen": [
        "阿伯丁", "Aberdeen", "Abd", "阿伯丁大学", "亚伯丁",
    ],
    "University of Stirling": [
        "斯特灵", "Stirling", "Stir", "斯特灵大学", "斯特林",
    ],
    "Edinburgh Napier University": [
        "龙比亚", "Napier", "爱丁堡龙比亚", "龙比亚大学",
    ],
    "Glasgow Caledonian University": [
        "卡利多尼亚", "GCU", "Caledonian", "格拉斯哥卡利多尼亚",
        "卡利多尼亚大学",
    ],
    "University of the West of Scotland": [
        "西苏格兰", "UWS", "West Scotland", "西苏格兰大学",
    ],
    "Robert Gordon University": [
        "罗伯特戈登", "RGU", "Robert Gordon", "戈登大学",
    ],
    "Abertay University": [
        "阿伯泰", "Abertay", "阿伯泰邓迪", "阿伯泰大学",
    ],
    "Queen Margaret University": [
        "玛格丽特女王", "QMU", "Queen Margaret", "玛格丽特女王大学",
    ],

    # ═══ 英格兰北部 ═══
    "University of Manchester": [
        "曼大", "曼彻斯特", "Manchester", "UoM", "曼城大学",
        "曼彻斯特大学", "曼城",
    ],
    "Manchester Metropolitan University": [
        "曼城大", "MMU", "曼彻斯特城市", "Manchester Met",
        "曼城都市大学", "曼彻斯特都会大学",
    ],
    "University of Salford": [
        "索尔福德", "Salford", "索尔福德大学", "索大",
    ],
    "University of Leeds": [
        "利大", "利兹", "Leeds", "利兹大学", "栗子大学",
    ],
    "Leeds Beckett University": [
        "利兹贝克特", "LBU", "Leeds Beckett", "贝克特大学",
    ],
    "University of Sheffield": [
        "谢大", "谢菲尔德", "Sheffield", "Shef", "谢菲",
        "谢菲尔德大学",
    ],
    "Sheffield Hallam University": [
        "哈勒姆", "SHU", "Sheffield Hallam", "谢菲尔德哈勒姆", "谢哈",
    ],
    "University of York": [
        "约大", "约克", "York", "约克大学",
    ],
    "York St John University": [
        "约克圣约翰", "YSJ", "York St John", "圣约翰大学",
    ],
    "Newcastle University": [
        "纽大", "纽卡斯尔", "Newcastle", "NCL", "纽卡",
        "纽卡斯尔大学",
    ],
    "Northumbria University": [
        "诺森比亚", "Northumbria", "诺桑比亚", "诺森比亚大学",
    ],
    "Durham University": [
        "杜伦", "Durham", "Dur", "杜伦大学", "达勒姆大学",
    ],
    "University of Hull": [
        "赫尔", "Hull", "赫尔大学",
    ],
    "University of Huddersfield": [
        "哈德斯菲尔德", "Huddersfield", "Hud", "哈德",
        "哈德斯菲尔德大学",
    ],
    "University of Bradford": [
        "布拉德福德", "Bradford", "Brad", "布拉德福德大学",
    ],
    "Teesside University": [
        "提赛德", "Teesside", "提赛德大学", "蒂赛德",
    ],
    "University of Sunderland": [
        "桑德兰", "Sunderland", "Sun", "桑德兰大学",
    ],

    # ═══ 英格兰中部 (Midlands) ═══
    "University of Birmingham": [
        "伯大", "伯明翰", "Birmingham", "Bham", "伯明翰大学",
    ],
    "Aston University": [
        "阿斯顿", "Aston", "阿斯顿大学",
    ],
    "Birmingham City University": [
        "伯城大", "BCU", "伯明翰城市", "Birmingham City",
        "伯明翰城市大学",
    ],
    "University of Warwick": [
        "华威", "Warwick", "Warw", "华威大学", "沃里克大学",
    ],
    "Coventry University": [
        "考文垂", "Coventry", "Cov", "考文垂大学",
    ],
    "University of Nottingham": [
        "诺大", "诺丁汉", "Nottingham", "UoN", "诺丁汉大学",
    ],
    "Nottingham Trent University": [
        "特伦特", "NTU", "Nottingham Trent", "诺丁汉特伦特",
        "特伦特大学",
    ],
    "University of Leicester": [
        "莱大", "莱斯特", "Leicester", "Leic", "莱斯特大学",
    ],
    "De Montfort University": [
        "德蒙福特", "DMU", "De Montfort", "德蒙", "德蒙福特大学",
    ],
    "Loughborough University": [
        "拉夫堡", "Lboro", "Loughborough", "拉夫堡大学", "拉大",
    ],
    "Keele University": [
        "基尔", "Keele", "基尔大学",
    ],
    "Staffordshire University": [
        "斯塔福德郡", "Staffs", "Staffordshire", "斯塔福德郡大学",
    ],
    "University of Derby": [
        "德比", "Derby", "德比大学",
    ],
    "University of Wolverhampton": [
        "伍尔弗汉普顿", "Wolves", "Wolverhampton", "伍尔弗汉普顿大学",
        "狼大",
    ],
    "University of Northampton": [
        "北安普顿", "Northampton", "北安普顿大学", "北安",
    ],
    "University of Lincoln": [
        "林肯", "Lincoln", "Linc", "林肯大学",
    ],

    # ═══ 英格兰西北 ═══
    "University of Liverpool": [
        "利物浦", "Liverpool", "Liv", "利物浦大学",
    ],
    "Liverpool John Moores University": [
        "约翰摩尔斯", "LJMU", "JMU", "利物浦约翰摩尔斯", "利物浦JMU",
    ],
    "Liverpool Hope University": [
        "利物浦霍普", "Hope", "Liverpool Hope", "霍普大学",
    ],
    "Lancaster University": [
        "兰卡", "兰卡斯特", "Lancaster", "Lancs", "兰卡斯特大学",
    ],
    "University of Central Lancashire": [
        "中央兰开夏", "UCLan", "中兰开夏", "普雷斯顿大学",
        "中央兰开夏大学",
    ],
    "Edge Hill University": [
        "边山", "EdgeHill", "Edge Hill", "边山大学",
    ],
    "University of Chester": [
        "切斯特", "Chester", "切斯特大学",
    ],
    "University of Cumbria": [
        "坎布里亚", "Cumbria", "坎布里亚大学",
    ],

    # ═══ 英格兰西南 ═══
    "University of Bristol": [
        "布大", "布里斯托", "Bristol", "Bris", "布里斯托大学",
    ],
    "University of the West of England": [
        "西英格兰", "UWE", "West England", "西英格兰大学",
        "布里斯托西英格兰",
    ],
    "University of Bath": [
        "巴斯", "Bath", "巴斯大学",
    ],
    "Bath Spa University": [
        "巴斯斯巴", "BathSpa", "Bath Spa", "巴斯泉大学",
    ],
    "University of Exeter": [
        "埃克塞特", "Exeter", "Exe", "埃克塞特大学", "艾克赛特",
    ],
    "University of Plymouth": [
        "普利茅斯", "Plymouth", "Plym", "普利茅斯大学",
    ],
    "Bournemouth University": [
        "伯恩茅斯", "BU", "Bournemouth", "伯恩茅斯大学",
    ],
    "Arts University Bournemouth": [
        "伯恩茅斯艺术", "AUB", "Arts Bournemouth", "伯恩茅斯艺术大学",
    ],
    "University of Gloucestershire": [
        "格洛斯特郡", "Glos", "Gloucestershire", "格洛斯特郡大学",
    ],
    "Falmouth University": [
        "法尔茅斯", "Falmouth", "法尔茅斯大学",
    ],
    "Royal Agricultural University": [
        "皇家农业", "RAU", "Royal Agricultural", "皇家农业大学",
    ],
    "Hartpury University": [
        "哈特伯瑞", "Hartpury", "哈特伯瑞大学",
    ],

    # ═══ 英格兰东南 ═══
    "University of Southampton": [
        "南安", "南安普顿", "Southampton", "Soton", "南安普敦",
        "南安普顿大学",
    ],
    "Solent University": [
        "索伦特", "Solent", "南安普顿索伦特", "索伦特大学",
    ],
    "University of Portsmouth": [
        "朴茨茅斯", "Portsmouth", "Port", "朴茨茅斯大学", "朴茅",
    ],
    "University of Sussex": [
        "萨塞克斯", "Sussex", "苏塞克斯", "萨塞克斯大学",
    ],
    "University of Brighton": [
        "布莱顿", "Brighton", "布莱顿大学",
    ],
    "University of Reading": [
        "雷丁", "Reading", "雷丁大学",
    ],
    "University of Surrey": [
        "萨里", "Surrey", "萨里大学", "吉尔福德大学",
    ],
    "University of Kent": [
        "肯特", "Kent", "坎特伯雷肯特", "肯特大学",
    ],
    "Canterbury Christ Church University": [
        "基督教会", "CCCU", "Christ Church", "坎特伯雷基督教会",
        "坎特伯雷教会大学",
    ],
    "University for the Creative Arts": [
        "创意艺术", "UCA", "Creative Arts", "创意艺术大学",
    ],
    "University of Chichester": [
        "奇切斯特", "Chichester", "Chich", "奇切斯特大学",
    ],
    "University of Winchester": [
        "温切斯特", "Winchester", "Winc", "温彻斯特", "温切斯特大学",
    ],
    "Buckinghamshire New University": [
        "白金汉郡", "BNU", "Bucks", "白金汉郡新大学",
    ],
    "University of Buckingham": [
        "白金汉", "Buckingham", "Buck", "白金汉大学",
    ],

    # ═══ 英格兰东部 ═══
    "University of East Anglia": [
        "东英吉利", "UEA", "East Anglia", "东安格利亚",
        "东英吉利亚大学", "东英吉利大学",
    ],
    "University of Essex": [
        "埃塞克斯", "Essex", "埃塞克斯大学",
    ],
    "University of Hertfordshire": [
        "赫特福德", "Herts", "Hertfordshire", "赫特福德大学",
        "赫特福德郡大学",
    ],
    "University of Bedfordshire": [
        "贝德福德郡", "Beds", "Bedfordshire", "贝德福德大学",
        "贝德福德郡大学",
    ],
    "Cranfield University": [
        "克兰菲尔德", "Cranfield", "克兰菲尔德大学", "克兰",
    ],
    "University of Suffolk": [
        "萨福克", "Suffolk", "萨福克大学",
    ],
    "Norwich University of the Arts": [
        "诺里奇艺术", "NUA", "Norwich Arts", "诺里奇艺术大学",
    ],

    # ═══ 威尔士 ═══
    "Cardiff University": [
        "卡大", "卡迪夫", "Cardiff", "卡迪夫大学", "卡的夫",
    ],
    "Cardiff Metropolitan University": [
        "卡迪夫城市", "CardiffMet", "UWIC", "卡迪夫都会",
        "卡迪夫城市大学",
    ],
    "Swansea University": [
        "斯旺西", "Swansea", "Swan", "斯旺西大学",
    ],
    "University of South Wales": [
        "南威尔士", "USW", "South Wales", "南威尔士大学",
    ],
    "Aberystwyth University": [
        "阿伯里斯特威斯", "Aberystwyth", "Aber", "阿伯大学",
        "阿伯里斯特威斯大学",
    ],
    "Bangor University": [
        "班戈", "Bangor", "班戈大学",
    ],
    "University of Wales Trinity Saint David": [
        "三一圣大卫", "UWTSD", "Trinity Saint David", "威尔士三一圣大卫",
        "三一圣大卫大学",
    ],
    "Wrexham University": [
        "雷克瑟姆", "Wrexham", "雷克瑟姆大学",
    ],

    # ═══ 北爱尔兰 ═══
    "Queen's University Belfast": [
        "贝法女王", "QUB", "Queen's Belfast", "女王大学",
        "贝尔法斯特女王", "贝尔法斯特女王大学", "贝法",
    ],
    "Ulster University": [
        "阿尔斯特", "Ulster", "阿尔斯特大学", "厄尔斯特大学",
    ],

    # ═══ 新加坡 ═══
    "National University of Singapore": [
        "NUS", "新加坡国立", "国大", "新国大", "新加坡国立大学",
    ],
    "Nanyang Technological University": [
        "NTU", "南洋理工", "南大", "南洋理工大学",
    ],
    "Singapore Management University": [
        "SMU", "新加坡管理", "新管大", "新加坡管理大学",
    ],
    "Singapore University of Technology and Design": [
        "SUTD", "新加坡科技设计", "新科大", "科技设计大学",
    ],
    "Singapore Institute of Technology": [
        "SIT", "新加坡理工", "新工大", "新加坡理工大学",
    ],
    "Singapore University of Social Sciences": [
        "SUSS", "新跃社科", "社科大学", "新跃大学",
    ],
    "LASALLE College of the Arts": [
        "拉萨尔", "LASALLE", "拉萨尔艺术", "拉萨尔艺术学院",
    ],
    "Nanyang Academy of Fine Arts": [
        "南洋艺术", "NAFA", "南艺", "南洋艺术学院",
    ],
    "INSEAD Asia Campus": [
        "INSEAD", "欧洲工商管理", "欧洲工商管理学院", "INSEAD亚洲",
    ],
    "James Cook University Singapore": [
        "JCU", "詹姆斯库克", "JCU新加坡", "詹姆斯库克大学",
    ],
    "Curtin University Singapore": [
        "Curtin", "科廷", "科廷新加坡", "科廷大学",
    ],
    "PSB Academy": [
        "PSB", "PSB学院", "PSB Academy",
    ],
    "Kaplan Higher Education Academy": [
        "Kaplan", "楷博", "楷博高等教育", "楷博学院",
    ],
    "Singapore Institute of Management": [
        "SIM", "新加坡管理", "新加坡管理学院",
    ],
    "Management Development Institute of Singapore": [
        "MDIS", "新加坡管理发展", "管理发展学院",
    ],
    "SP Jain School of Global Management": [
        "SPJ", "SP Jain", "SPJain全球管理",
    ],
    "Ngee Ann Polytechnic": [
        "义安理工", "NP", "义安理工学院",
    ],
    "Singapore Polytechnic": [
        "新加坡理工", "SP", "新加坡理工学院",
    ],
    "Temasek Polytechnic": [
        "淡马锡理工", "TP", "淡马锡理工学院",
    ],
    "Nanyang Polytechnic": [
        "南洋理工", "NYP", "南洋理工学院",
    ],
    "Republic Polytechnic": [
        "共和理工", "RP", "共和理工学院",
    ],
}


def upgrade() -> None:
    conn = op.get_bind()
    for university_name, aliases_list in ALIASES.items():
        arr = "{" + ",".join(f'"{a}"' for a in aliases_list) + "}"
        conn.execute(
            text("UPDATE universities SET aliases = CAST(:aliases AS varchar(50)[]) WHERE name = :name"),
            {"aliases": arr, "name": university_name},
        )


def downgrade() -> None:
    # 回滚到简洁版别名
    RESTORE = {
        "Imperial College London": "帝国理工",
        "University College London": "UCL",
        "King's College London": "国王学院",
        "London School of Economics and Political Science": "伦敦政经;LSE",
        "University of Manchester": "曼大;UoM",
        "University of Edinburgh": "爱大;Edin",
        "University of Glasgow": "格大;Glas",
        "University of St Andrews": "圣安;StA",
        "University of Birmingham": "伯大;Bham",
        "University of Bristol": "布大;Bris",
        "University of Leeds": "利大;Leeds",
        "University of Sheffield": "谢大;Shef",
        "University of York": "约大;York",
        "Newcastle University": "纽大;NCL",
        "Durham University": "杜伦;Dur",
        "University of Liverpool": "利物浦;Liv",
        "Lancaster University": "兰卡;Lancs",
        "University of Bath": "巴斯;Bath",
        "University of Exeter": "埃克塞特;Exe",
        "University of Southampton": "南安;Soton",
        "Cardiff University": "卡大;Cardiff",
        "Queen's University Belfast": "贝法女王;QUB",
        "National University of Singapore": "NUS",
        "Nanyang Technological University": "NTU",
        "Singapore Management University": "SMU",
    }
    conn = op.get_bind()
    for name, aliases_str in RESTORE.items():
        aliases = [a.strip() for a in aliases_str.split(";")]
        arr = "{" + ",".join(f'"{a}"' for a in aliases) + "}"
        conn.execute(
            text("UPDATE universities SET aliases = CAST(:aliases AS varchar(50)[]) WHERE name = :name"),
            {"aliases": arr, "name": name},
        )

"""安全评分子系统 —— 对接外部犯罪/安全数据源

已实现:
- 新加坡: data.gov.sg (Selected Major Offences by NPC)
- 英国: Police.uk API (待实现)

NPC 映射策略：预加载 35 个 NPC 中心坐标，取最近 NPC 匹配犯罪数据。
后续可升级为 OneMap API Point-in-Polygon 精确判断。
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════

NEUTRAL_SAFETY = 60.0

# data.gov.sg API
DATAGOV_BASE = "https://data.gov.sg/api/action/datastore_search"
SG_CRIME_RESOURCE_ID = "d_5767147db6e5b4c4cfa874db132fef39"  # Selected Major Offences by NPC
SG_UML_RESOURCE_ID = "d_b6dc6308d208f668232b4f9e171af3a4"    # Unlicensed Moneylending by NPC

REQUEST_TIMEOUT = 15.0
CACHE_TTL_SECONDS = 86_400  # 24h — 数据年度更新

# ═══════════════════════════════════════════════════════
# 新加坡 NPC 中心坐标（35 个邻里警局）
# 用于最近 NPC 匹配——后续升级为 OneMap Point-in-Polygon
# ═══════════════════════════════════════════════════════

SG_NPC_CENTERS: dict[str, tuple[float, float]] = {
    "Ang Mo Kio NPC": (1.3691, 103.8488),
    "Bedok NPC": (1.3236, 103.9303),
    "Bukit Batok NPC": (1.3491, 103.7496),
    "Bukit Merah NPC": (1.2821, 103.8266),
    "Bukit Panjang NPC": (1.3786, 103.7625),
    "Bukit Timah NPC": (1.3294, 103.8021),
    "Central NPC": (1.2800, 103.8500),
    "Changi NPC": (1.3430, 103.9620),
    "Clementi NPC": (1.3152, 103.7648),
    "Geylang NPC": (1.3179, 103.8874),
    "Hougang NPC": (1.3716, 103.8930),
    "Jurong East NPC": (1.3329, 103.7436),
    "Jurong West NPC": (1.3404, 103.7065),
    "Kallang NPC": (1.3102, 103.8662),
    "Kampong Glam NPC": (1.3020, 103.8590),
    "Marina Bay NPC": (1.2806, 103.8570),
    "Nee Soon NPC": (1.4050, 103.8300),
    "Orchard NPC": (1.3048, 103.8318),
    "Pasir Ris NPC": (1.3739, 103.9523),
    "Punggol NPC": (1.4010, 103.9075),
    "Queenstown NPC": (1.2940, 103.8000),
    "Sembawang NPC": (1.4510, 103.8210),
    "Sengkang NPC": (1.3906, 103.8900),
    "Serangoon NPC": (1.3516, 103.8710),
    "Tampines NPC": (1.3531, 103.9443),
    "Tanglin NPC": (1.3060, 103.8200),
    "Toa Payoh NPC": (1.3343, 103.8563),
    "Woodlands NPC": (1.4360, 103.7860),
    "Woodlands East NPC": (1.4420, 103.7960),
    "Yishun North NPC": (1.4360, 103.8350),
    "Yishun South NPC": (1.4250, 103.8350),
}

# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

@dataclass
class SafetyResult:
    """统一安全评分输出"""
    property_id: int
    score: float                     # 0-100，越高越安全
    data_source: str = "stub"        # "data.gov.sg" / "police.uk"
    data_period: str = ""            # e.g. "2024"
    npc: str = ""                    # 新加坡: NPC 辖区名

    # 分类明细 (per 100k residents)
    housebreaking_rate: float = 0.0
    outrage_of_modesty_rate: float = 0.0
    robbery_rate: float = 0.0
    snatch_theft_rate: float = 0.0
    motor_theft_rate: float = 0.0
    uml_harassment_rate: float = 0.0

    # 对比
    vs_national_avg: str = "average"  # "below" / "average" / "above"
    national_avg_rate: float = 0.0

    # 摘要
    summary: str = ""

    # 原始数据
    raw_data: dict | None = None

    def to_dict(self) -> dict:
        return {
            "property_id": self.property_id,
            "safety_score": self.score,
            "data_source": self.data_source,
            "data_period": self.data_period,
            "npc": self.npc,
            "category_breakdown": {
                "housebreaking_rate": self.housebreaking_rate,
                "outrage_of_modesty_rate": self.outrage_of_modesty_rate,
                "robbery_rate": self.robbery_rate,
                "snatch_theft_rate": self.snatch_theft_rate,
                "motor_theft_rate": self.motor_theft_rate,
                "uml_harassment_rate": self.uml_harassment_rate,
            },
            "comparison": {
                "vs_national_avg": self.vs_national_avg,
                "national_avg_rate": self.national_avg_rate,
            },
            "summary": self.summary,
        }


# ═══════════════════════════════════════════════════════
# 服务
# ═══════════════════════════════════════════════════════

class SafetyScoringService:
    """安全评分服务 — 新加坡 data.gov.sg 管线已实现"""

    def __init__(self) -> None:
        self._crime_cache: dict | None = None        # 犯罪数据缓存
        self._uml_cache: dict | None = None          # UML 数据缓存
        self._cache_time: float = 0.0                # 缓存时间戳

    # ── 公共接口 ────────────────────────────────────

    async def score_properties(
        self,
        property_ids: list[int],
        country: str | None = None,
        latitudes: dict[int, float] | None = None,   # {property_id: lat}
        longitudes: dict[int, float] | None = None,  # {property_id: lng}
    ) -> dict[int, SafetyResult]:
        """对一批房源进行安全评分。

        Args:
            property_ids: 房源 ID 列表
            country: 国家代码（sg / uk）
            latitudes / longitudes: 房源坐标映射
        """
        is_sg = country and country.upper() == "SG"
        if not is_sg:
            # 非 SG 暂时回退到中性分（UK 待实现）
            logger.info("安全评分: %d 套房源, country=%s → 中性分（仅 SG 支持）",
                        len(property_ids), country)
            return {
                pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
                for pid in property_ids
            }

        # 检查坐标
        if not latitudes or not longitudes:
            logger.warning("安全评分 SG: 缺少坐标数据，返回中性分")
            return {
                pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
                for pid in property_ids
            }

        try:
            crime_data, uml_data = await self._fetch_sg_data()
            national = self._compute_national_avg(crime_data, uml_data)

            results: dict[int, SafetyResult] = {}
            for pid in property_ids:
                lat = latitudes.get(pid)
                lng = longitudes.get(pid)
                if lat is None or lng is None:
                    results[pid] = SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
                    continue
                results[pid] = self._score_single_sg(pid, lat, lng, crime_data, uml_data, national)

            logger.info("安全评分 SG: %d 套房源完成", len(results))
            return results

        except Exception:
            logger.exception("安全评分 SG 失败，回退中性分")
            return {
                pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
                for pid in property_ids
            }

    async def score_single(
        self, property_id: int, lat: float | None = None,
        lng: float | None = None, country: str | None = None,
    ) -> SafetyResult:
        lats = {property_id: lat} if lat is not None else {}
        lngs = {property_id: lng} if lng is not None else {}
        results = await self.score_properties([property_id], country, lats, lngs)
        return results[property_id]

    # ── data.gov.sg API ─────────────────────────────

    async def _fetch_sg_data(self) -> tuple[dict, dict]:
        """获取新加坡犯罪数据（带缓存）"""
        now = asyncio.get_event_loop().time()
        if self._crime_cache and self._uml_cache and (now - self._cache_time) < CACHE_TTL_SECONDS:
            return self._crime_cache, self._uml_cache

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # 主要犯罪数据
            crime_records = await self._fetch_datagov_resource(client, SG_CRIME_RESOURCE_ID)
            # UML 非法放贷数据
            uml_records = await self._fetch_datagov_resource(client, SG_UML_RESOURCE_ID)

        self._crime_cache = crime_records
        self._uml_cache = uml_records
        self._cache_time = now

        logger.info("data.gov.sg 缓存更新: %d NPC 犯罪记录, %d UML 记录",
                    len(crime_records), len(uml_records))
        return crime_records, uml_records

    @staticmethod
    async def _fetch_datagov_resource(client: httpx.AsyncClient, resource_id: str) -> dict:
        """分页拉取 data.gov.sg 全量数据，返回 {npc: {fields}} 字典"""
        records: dict[str, dict] = {}
        offset = 0
        while True:
            try:
                r = await client.get(
                    DATAGOV_BASE,
                    params={"resource_id": resource_id, "limit": 100, "offset": offset},
                )
                if r.status_code != 200:
                    logger.warning("data.gov.sg %s: HTTP %s", resource_id[:12], r.status_code)
                    break
                data = r.json()
                if not data.get("success"):
                    break
                result = data.get("result", {})
                recs = result.get("records", [])
                if not recs:
                    break
                for rec in recs:
                    npc = (rec.get("npc") or "").strip()
                    if npc:
                        records[npc] = rec
                offset += len(recs)
                if offset >= result.get("total", 0):
                    break
            except httpx.HTTPError:
                logger.exception("data.gov.sg 请求失败")
                break
        return records

    # ── NPC 匹配 ────────────────────────────────────

    @staticmethod
    def _find_nearest_npc(lat: float, lng: float) -> str:
        """找到最近的 NPC 辖区"""
        best_npc = "Central NPC"
        best_dist = float("inf")
        for npc_name, (npc_lat, npc_lng) in SG_NPC_CENTERS.items():
            d = _hav_distance(lat, lng, npc_lat, npc_lng)
            if d < best_dist:
                best_dist = d
                best_npc = npc_name
        return best_npc

    # ── 评分计算 ────────────────────────────────────

    @staticmethod
    def _compute_national_avg(crime_data: dict, uml_data: dict) -> dict:
        """计算全国加权平均犯罪率 (per 100k)"""
        # 新加坡 ~5.9M 人口
        pop = 5_920_000
        total = {
            "housebreaking": 0, "outrage_of_modesty": 0,
            "robbery": 0, "snatch_theft": 0, "motor_theft": 0,
            "uml_harassment": 0,
        }
        for rec in crime_data.values():
            total["housebreaking"] += _safe_int(rec.get("housebreaking"))
            total["outrage_of_modesty"] += _safe_int(rec.get("outrage_of_modesty"))
            total["robbery"] += _safe_int(rec.get("robbery"))
            total["snatch_theft"] += _safe_int(rec.get("snatch_theft"))
            total["motor_theft"] += _safe_int(rec.get("theft_of_motor_vehicle"))
        for rec in uml_data.values():
            total["uml_harassment"] += _safe_int(rec.get("harassment"))

        return {k: v / pop * 100_000 for k, v in total.items()}

    @staticmethod
    def _score_single_sg(
        property_id: int, lat: float, lng: float,
        crime_data: dict, uml_data: dict, national: dict,
    ) -> SafetyResult:
        """对单个新加坡房源评分"""
        npc = SafetyScoringService._find_nearest_npc(lat, lng)

        # 从数据中查找 NPC 记录
        crime_rec = crime_data.get(npc, {})
        uml_rec = uml_data.get(npc, {})

        # 提取各分类计数
        counts = {
            "housebreaking": _safe_int(crime_rec.get("housebreaking")),
            "outrage_of_modesty": _safe_int(crime_rec.get("outrage_of_modesty")),
            "robbery": _safe_int(crime_rec.get("robbery")),
            "snatch_theft": _safe_int(crime_rec.get("snatch_theft")),
            "motor_theft": _safe_int(crime_rec.get("theft_of_motor_vehicle")),
            "uml_harassment": _safe_int(uml_rec.get("harassment")),
        }

        # 权重（设计文档定义）
        weights = {
            "housebreaking": 0.35,
            "outrage_of_modesty": 0.30,
            "robbery": 0.12,
            "snatch_theft": 0.08,
            "motor_theft": 0.10,
            "uml_harassment": 0.05,
        }

        # NPC 辖区人口粗略估算（35 个 NPC，均匀分布 ~169k/辖区）
        # 更精确的做法：data.gov.sg 人口数据或 OneMap planning area 人口
        npc_pop = 5_920_000 / 35  # ~169k

        # 加权计算
        zone_weighted = sum(
            counts[cat] / npc_pop * 100_000 * weights[cat]
            for cat in weights
        )
        national_weighted = sum(national.get(cat, 0) * weights[cat] for cat in weights)

        # 评分公式: ratio = zone / national, score = clamp(100 - ratio × 50, 10, 100)
        if national_weighted > 0:
            ratio = zone_weighted / national_weighted
        else:
            ratio = 1.0

        raw_score = 100 - ratio * 50
        score = max(10.0, min(100.0, raw_score))

        # 对比
        if ratio < 0.75:
            vs_national = "below"
        elif ratio > 1.25:
            vs_national = "above"
        else:
            vs_national = "average"

        # 年份
        year = str(crime_rec.get("year") or uml_rec.get("year") or "")

        # 摘要
        summary = _build_sg_summary(npc, counts, vs_national, ratio)

        return SafetyResult(
            property_id=property_id,
            score=round(score, 1),
            data_source="data.gov.sg",
            data_period=year,
            npc=npc,
            housebreaking_rate=round(counts["housebreaking"] / npc_pop * 100_000, 1),
            outrage_of_modesty_rate=round(counts["outrage_of_modesty"] / npc_pop * 100_000, 1),
            robbery_rate=round(counts["robbery"] / npc_pop * 100_000, 1),
            snatch_theft_rate=round(counts["snatch_theft"] / npc_pop * 100_000, 1),
            motor_theft_rate=round(counts["motor_theft"] / npc_pop * 100_000, 1),
            uml_harassment_rate=round(counts["uml_harassment"] / npc_pop * 100_000, 1),
            vs_national_avg=vs_national,
            national_avg_rate=round(national_weighted, 1),
            summary=summary,
            raw_data={"counts": counts, "npc": npc, "year": year},
        )


# ═══════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════

def _hav_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 距离（米）"""
    R = 6_371_000
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _safe_int(val) -> int:
    """安全转 int，处理空值和字符串"""
    if val is None:
        return 0
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return 0


def _build_sg_summary(npc: str, counts: dict, vs_national: str, ratio: float) -> str:
    """生成新加坡安全摘要"""
    total_crimes = sum(counts.values())
    level = {
        "below": "低于",
        "average": "接近",
        "above": "高于",
    }.get(vs_national, "接近")

    main_risks = []
    if counts.get("housebreaking", 0) > 0:
        main_risks.append(f"破门行窃 {counts['housebreaking']} 起")
    if counts.get("outrage_of_modesty", 0) > 0:
        main_risks.append(f"非礼 {counts['outrage_of_modesty']} 起")

    risk_text = "、".join(main_risks[:2]) if main_risks else "各类犯罪案件较少"

    return (
        f"{npc} 辖区年度记录 {risk_text}，"
        f"共 {total_crimes} 起可防罪案。"
        f"加权犯罪率{level}全国均值（{ratio:.1%}）。"
        f"新加坡整体治安良好，但仍建议实地考察周边环境。"
    )

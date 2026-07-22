"""安全评分子系统 —— 对接外部犯罪/安全数据源

已实现:
- 新加坡: 本地预存 data.gov.sg 年度 NPC 犯罪数据（零 API 调用）
- 英国: CrystalRoof (crystalroof.co.uk 街区犯罪评分)

NPC 映射策略：data.gov.sg NPC Boundary GeoJSON + Point-in-Polygon 精确匹配。
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx  # 仅 UK CrystalRoof 需要

from app.core.config import get_settings
from app.services.sg_crime_data import SG_CRIME_RECORDS
from app.services.sg_npc_mapping import find_npc_by_boundary, NPC_CODE_MAP

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════

NEUTRAL_SAFETY = 3.0  # 5 分制中性分
REQUEST_TIMEOUT = 15.0  # UK CrystalRoof 超时

# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

@dataclass
class SafetyResult:
    """统一安全评分输出"""
    property_id: int
    score: float                     # 5 分制，越高越安全 (0.0-5.0)
    data_source: str = "stub"        # "data.gov.sg" / "crystalroof.co.uk"
    data_period: str = ""            # e.g. "2024"
    npc: str = ""                    # 新加坡: NPC 辖区名

    # 新加坡: 非礼专项评分 (3.0-5.0, 仅 SG 有值)
    om_score: float = 0.0

    # 新加坡分类明细 (per 100k residents)
    housebreaking_rate: float = 0.0
    outrage_of_modesty_rate: float = 0.0
    robbery_rate: float = 0.0
    snatch_theft_rate: float = 0.0
    motor_theft_rate: float = 0.0

    # 英国分类明细 (CrystalRoof crime, 5 分制)
    uk_crime_score: float = 0.0

    # 对比
    vs_national_avg: str = "average"
    national_avg_rate: float = 0.0

    # 外链
    report_url: str = ""

    # 摘要
    summary: str = ""

    # 原始数据
    raw_data: dict | None = None

    def to_dict(self) -> dict:
        d = {
            "property_id": self.property_id,
            "safety_score": self.score,
            "data_source": self.data_source,
            "data_period": self.data_period,
            "npc": self.npc,
            "summary": self.summary,
            "report_url": self.report_url,
        }
        if self.data_source == "data.gov.sg":
            d["om_score"] = self.om_score
            d["category_breakdown"] = {
                "housebreaking_rate": self.housebreaking_rate,
                "robbery_rate": self.robbery_rate,
                "snatch_theft_rate": self.snatch_theft_rate,
                "motor_theft_rate": self.motor_theft_rate,
            }
            d["comparison"] = {
                "vs_national_avg": self.vs_national_avg,
                "national_avg_rate": self.national_avg_rate,
            }
        elif self.data_source == "crystalroof.co.uk":
            d["category_breakdown"] = {"crime": self.uk_crime_score}
        return d


# ═══════════════════════════════════════════════════════
# 服务
# ═══════════════════════════════════════════════════════

class SafetyScoringService:
    """安全评分服务 — SG 本地数据 / UK CrystalRoof"""

    # ── 公共接口 ────────────────────────────────────

    async def score_properties(
        self,
        property_ids: list[int],
        country: str | None = None,
        latitudes: dict[int, float] | None = None,
        longitudes: dict[int, float] | None = None,
    ) -> dict[int, SafetyResult]:
        country_upper = (country or "").upper()

        if country_upper == "SG":
            return self._score_sg_batch(property_ids, latitudes, longitudes)

        if country_upper in ("GB", "UK"):
            return await self._score_uk_batch(property_ids, latitudes, longitudes)

        logger.info("安全评分: %d 套房源, country=%s → 中性分", len(property_ids), country)
        return {pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY) for pid in property_ids}

    # ── 新加坡（本地数据，零 API 调用）───────────────

    def _score_sg_batch(
        self, property_ids: list[int],
        latitudes: dict[int, float] | None,
        longitudes: dict[int, float] | None,
    ) -> dict[int, SafetyResult]:
        if not latitudes or not longitudes:
            logger.warning("安全评分 SG: 缺少坐标数据，返回中性分")
            return {pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY) for pid in property_ids}
        if not SG_CRIME_RECORDS:
            logger.warning("安全评分 SG: 本地数据为空，运行 --refresh 拉取 data.gov.sg 数据")
            return {pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY) for pid in property_ids}

        national = self._compute_national_avg(SG_CRIME_RECORDS)
        results: dict[int, SafetyResult] = {}
        for pid in property_ids:
            lat = latitudes.get(pid)
            lng = longitudes.get(pid)
            if lat is None or lng is None:
                results[pid] = SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
                continue
            results[pid] = self._score_single_sg(pid, lat, lng, SG_CRIME_RECORDS, national)
        logger.info("安全评分 SG: %d 套房源完成（本地数据）", len(results))
        return results

    # ── 英国（Police.uk 1英里半径原始案件）───────────

    # 评分权重（设计文档定义）
    UK_WEIGHTS = {
        "violent-crime": 0.35,
        "burglary": 0.25,
        "robbery": 0.15,
        "anti-social-behaviour": 0.15,
        "vehicle-crime": 0.10,
    }
    UK_DIVISOR = 150  # 加权总数/150 = 扣分

    async def _score_uk_batch(
        self, property_ids: list[int],
        latitudes: dict[int, float] | None,
        longitudes: dict[int, float] | None,
    ) -> dict[int, SafetyResult]:
        if not latitudes or not longitudes:
            logger.warning("安全评分 UK: 缺少坐标数据，返回中性分")
            return {pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY) for pid in property_ids}
        try:
            import httpx
            results: dict[int, SafetyResult] = {}
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                for pid in property_ids:
                    lat = latitudes.get(pid)
                    lng = longitudes.get(pid)
                    if lat is None or lng is None:
                        results[pid] = SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
                        continue
                    try:
                        r = await client.get(
                            "https://data.police.uk/api/crimes-street/all-crime",
                            params={"lat": lat, "lng": lng, "date": self._latest_police_month()},
                        )
                        if r.status_code != 200:
                            logger.warning("Police.uk API: HTTP %s for pid=%s", r.status_code, pid)
                            results[pid] = SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
                            continue
                        crimes = r.json()
                        # 按类别计数
                        counts: dict[str, int] = {}
                        for c in crimes:
                            cat = c.get("category", "other-crime")
                            counts[cat] = counts.get(cat, 0) + 1
                        # 加权
                        weighted = sum(
                            counts.get(cat, 0) * w
                            for cat, w in self.UK_WEIGHTS.items()
                        )
                        raw_score = 5.0 - weighted / self.UK_DIVISOR
                        score = round(max(1.0, min(5.0, raw_score)), 1)

                        # 明细
                        breakdown = {
                            "violent_crime": counts.get("violent-crime", 0),
                            "burglary": counts.get("burglary", 0),
                            "robbery": counts.get("robbery", 0),
                            "anti_social_behaviour": counts.get("anti-social-behaviour", 0),
                            "vehicle_crime": counts.get("vehicle-crime", 0),
                        }
                        total = sum(counts.values())
                        summary = (
                            f"1英里半径内近一月记录 {total} 起案件，"
                            f"其中暴力犯罪 {breakdown['violent_crime']} 起、"
                            f"入室盗窃 {breakdown['burglary']} 起。"
                            f"安全评分 {score}/5.0。"
                        )
                        results[pid] = SafetyResult(
                            property_id=pid,
                            score=score,
                            data_source="data.police.uk",
                            data_period=self._latest_police_month(),
                            uk_crime_score=score,
                            summary=summary,
                            raw_data={
                                "counts": counts,
                                "weighted": round(weighted, 1),
                                "total": total,
                                "lat": lat, "lng": lng,
                            },
                        )
                    except Exception:
                        logger.exception("Police.uk 评分失败 pid=%s", pid)
                        results[pid] = SafetyResult(property_id=pid, score=NEUTRAL_SAFETY)
            logger.info("安全评分 UK: %d 套房源完成", len(results))
            return results
        except Exception:
            logger.exception("安全评分 UK 失败，回退中性分")
            return {pid: SafetyResult(property_id=pid, score=NEUTRAL_SAFETY) for pid in property_ids}

    @staticmethod
    def _latest_police_month() -> str:
        """Police.uk 数据通常滞后 1-2 个月，返回最近可用月份"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        # 回退 2 个月确保数据已发布
        target = now.replace(day=1)
        if target.month <= 2:
            target = target.replace(year=target.year - 1, month=target.month + 10)
        else:
            target = target.replace(month=target.month - 2)
        return target.strftime("%Y-%m")

    async def score_single(
        self, property_id: int, lat: float | None = None,
        lng: float | None = None, country: str | None = None,
    ) -> SafetyResult:
        lats = {property_id: lat} if lat is not None else {}
        lngs = {property_id: lng} if lng is not None else {}
        results = await self.score_properties(
            [property_id], country, lats, lngs,
        )
        return results[property_id]

    # ── 评分计算 ────────────────────────────────────

    @staticmethod
    def _compute_national_avg(crime_data: dict) -> dict:
        """计算全国加权平均犯罪率 (per 100k)"""
        pop = 5_920_000
        total = {"housebreaking": 0, "robbery": 0, "snatch_theft": 0, "motor_theft": 0}
        for rec in crime_data.values():
            total["housebreaking"] += rec.get("Housebreaking", 0)
            total["robbery"] += rec.get("Robbery", 0)
            total["snatch_theft"] += rec.get("Snatch Theft", 0)
            total["motor_theft"] += rec.get("Theft Of Motor Vehicle", 0)
        return {k: v / pop * 100_000 for k, v in total.items()}

    @staticmethod
    def _score_single_sg(
        property_id: int, lat: float, lng: float,
        crime_data: dict, national: dict,
    ) -> SafetyResult:
        """对单个新加坡房源评分"""
        # Point-in-Polygon 精确匹配 NPC，失败回退到最近邻
        npc_code = find_npc_by_boundary(lat, lng)
        npc = NPC_CODE_MAP.get(npc_code or "", "") if npc_code else ""

        # 从数据中查找 NPC 记录
        crime_rec = crime_data.get(npc, {})

        # 提取各分类计数（4 类：破门/抢劫/抢夺/偷车）
        counts = {
            "housebreaking": crime_rec.get("Housebreaking", 0),
            "outrage_of_modesty": crime_rec.get("Outrage Of Modesty", 0),
            "robbery": crime_rec.get("Robbery", 0),
            "snatch_theft": crime_rec.get("Snatch Theft", 0),
            "motor_theft": crime_rec.get("Theft Of Motor Vehicle", 0),
        }

        # 主评分权重（不含非礼，总和 0.65 → 归一化）
        raw_weights = {
            "housebreaking": 0.35,
            "robbery": 0.12,
            "snatch_theft": 0.08,
            "motor_theft": 0.10,
        }
        w_sum = sum(raw_weights.values())  # 0.65
        weights = {k: v / w_sum for k, v in raw_weights.items()}

        # NPC 辖区人口估算
        npc_pop = 5_920_000 / 35  # ~169k

        # 加权计算（不含非礼）
        zone_weighted = sum(
            counts[cat] / npc_pop * 100_000 * weights[cat]
            for cat in weights
        )
        national_weighted = sum(national.get(cat, 0) * weights[cat] for cat in weights)

        # ── 主安全评分（放宽: 惩罚系数 50→30，新加坡基线友好）──
        if national_weighted > 0:
            ratio = zone_weighted / national_weighted
        else:
            ratio = 1.0
        score_100 = max(10.0, min(100.0, 100.0 - ratio * 15.0))
        score = round(score_100 / 20.0, 1)

        # ── 非礼专项评分（连续制，3.6-5.0）──
        om_cases = counts["outrage_of_modesty"]
        om_per_100k = om_cases / npc_pop * 100_000
        om_score = max(3.6, min(5.0, round(5.0 - (om_per_100k - 10) / 30, 1)))

        # 对比
        if ratio < 0.75:
            vs_national = "below"
        elif ratio > 1.25:
            vs_national = "above"
        else:
            vs_national = "average"

        summary = _build_sg_summary(npc, counts, vs_national, ratio, score, om_score)

        return SafetyResult(
            property_id=property_id,
            score=score,
            om_score=om_score,
            data_source="data.gov.sg",
            data_period="2024",
            npc=npc,
            housebreaking_rate=round(counts["housebreaking"] / npc_pop * 100_000, 1),
            outrage_of_modesty_rate=round(counts["outrage_of_modesty"] / npc_pop * 100_000, 1),
            robbery_rate=round(counts["robbery"] / npc_pop * 100_000, 1),
            snatch_theft_rate=round(counts["snatch_theft"] / npc_pop * 100_000, 1),
            motor_theft_rate=round(counts["motor_theft"] / npc_pop * 100_000, 1),
            vs_national_avg=vs_national,
            national_avg_rate=round(national_weighted, 1),
            summary=summary,
            raw_data={"counts": counts, "npc": npc, "year": "2024"},
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


def _build_sg_summary(npc: str, counts: dict, vs_national: str,
                      ratio: float, score: float, om_score: float) -> str:
    """生成新加坡安全摘要"""
    total_crimes = sum(counts.values())
    level = {"below": "低于", "average": "接近", "above": "高于"}.get(vs_national, "接近")

    main_risks = []
    if counts.get("housebreaking", 0) > 0:
        main_risks.append(f"破门行窃 {counts['housebreaking']} 起")
    risk_text = "、".join(main_risks[:2]) if main_risks else "各类犯罪案件较少"

    short_npc = npc.split(" - ")[-1].replace(" NPC", "") if " - " in npc else npc
    return (
        f"{short_npc} 辖区年度记录 {risk_text}，"
        f"共 {total_crimes} 起可防罪案。"
        f"综合安全 {score}/5.0（{level}全国均值），"
        f"非礼专项 {om_score}/5.0。"
        f"新加坡整体治安良好，但仍建议实地考察周边环境。"
    )

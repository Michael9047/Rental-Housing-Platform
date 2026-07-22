"""安全评分子系统 —— 对接外部犯罪/安全数据源

当前为 MVP stub：全部返回中性分 60。
后续替换为真实数据源：
- 英国: Police.uk API (data.police.uk/crimes-street)
- 新加坡: data.gov.sg (Selected Major Offences by NPC)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NEUTRAL_SAFETY = 60.0


@dataclass
class SafetyResult:
    property_id: int
    score: float          # 0-100，越高越安全
    violent_rate: float   # per 1000 residents
    burglary_rate: float
    vs_city_avg: str      # "below" / "average" / "above"
    summary: str          # 一句话描述


class SafetyScoringService:
    """安全评分服务 —— 当前为中性 stub，后续接入真实数据。"""

    async def score_properties(
        self,
        property_ids: list[int],
        country: str | None = None,
    ) -> dict[int, SafetyResult]:
        """对一批房源进行安全评分。

        Args:
            property_ids: 房源 ID 列表
            country: 国家代码（uk / sg），用于路由数据源

        Returns:
            {property_id: SafetyResult}
        """
        logger.info(
            "安全评分 stub: %d 套房源, country=%s → 返回中性分",
            len(property_ids), country,
        )
        return {
            pid: SafetyResult(
                property_id=pid,
                score=NEUTRAL_SAFETY,
                violent_rate=0.0,
                burglary_rate=0.0,
                vs_city_avg="average",
                summary="安全数据暂未接入，使用中性评分占位。",
            )
            for pid in property_ids
        }

    async def score_single(
        self, property_id: int, country: str | None = None
    ) -> SafetyResult:
        results = await self.score_properties([property_id], country)
        return results[property_id]

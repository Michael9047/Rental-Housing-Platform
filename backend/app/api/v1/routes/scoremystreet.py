"""ScoreMyStreet 评分路由 - 根据 UK 地址查询其在 scoremystreet.com 的评分"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.scoremystreet_service import (
    get_scoremystreet_score,
    is_uk_address,
)

router = APIRouter()


@router.get("/score")
async def get_score(
    address: str = Query(..., min_length=1, max_length=500),
    country: str | None = Query(default=None, max_length=8),
) -> dict:
    """根据地址获取 ScoreMyStreet 评分信息

    返回的字段：
    - postcode: 邮编
    - report_url: 报告页 URL
    - search_url: 搜索页 URL
    - overall_score: 0-100 的综合评分
    - safety_score: 安全评分（0-5）
    - schools_score: 学校评分（0-100）
    - amenities_score: 设施评分（0-100）
    - transport_score: 交通评分（0-100）
    - connectivity_score: 网络评分（0-100）
    - area_name: 区域名称
    - crime_count: 近6个月犯罪数量
    - fetched: 是否成功从网站抓取并解析到评分
    - source: 数据来源
    """
    if not is_uk_address(address, country):
        raise HTTPException(
            status_code=400,
            detail="ScoreMyStreet 仅支持英国地址，请确认地址属于 UK",
        )

    result = await get_scoremystreet_score(address)
    return result.to_dict()

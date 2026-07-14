"""CrystalRoof 评分路由 - 根据 UK 地址查询其在 crystalroof.co.uk 的评分"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.crystalroof_service import (
    get_crystalroof_score,
    is_uk_address,
)

router = APIRouter()


class CrystalRoofScoreRequest(BaseModel):
    address: str = Field(..., min_length=1, max_length=500, description="完整地址")
    country: str | None = Field(default=None, max_length=8, description="国家代码（如 GB）")


@router.get("/score")
async def get_score(
    address: str = Query(..., min_length=1, max_length=500),
    country: str | None = Query(default=None, max_length=8),
) -> dict:
    """根据地址获取 CrystalRoof 评分信息

    返回的字段：
    - address: 原始地址
    - search_url: CrystalRoof 搜索页 URL（始终返回）
    - report_url: 报告页 URL（如果能识别 postcode）
    - overall_score: 0-100 的整体评分（解析失败时为 null）
    - subscores: 子项评分（crime/schools/transport 等）
    - fetched: 是否成功从网站抓取并解析到评分
    - source: 数据来源
    """
    if not is_uk_address(address, country):
        raise HTTPException(
            status_code=400,
            detail="CrystalRoof 仅支持英国地址，请确认地址属于 UK",
        )

    result = await get_crystalroof_score(address)
    return result.to_dict()


@router.post("/score")
async def post_score(req: CrystalRoofScoreRequest) -> dict:
    """POST 版本，支持通过 JSON body 传递参数"""
    if not is_uk_address(req.address, req.country):
        raise HTTPException(
            status_code=400,
            detail="CrystalRoof 仅支持英国地址，请确认地址属于 UK",
        )
    result = await get_crystalroof_score(req.address)
    return result.to_dict()

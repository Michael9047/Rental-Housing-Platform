"""AI 搜房 —— 自然语言解析 + 智能检索 + 摘要生成"""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.ai_search import (
    AiSearchRequest,
    AiSearchResponse,
    ParseRequest,
    ParseResponse,
)
from app.schemas.property import PropertySearchResult
from app.schemas.property_image import PropertyImageRead
from app.services.llm_service import get_llm_service
from app.services.property_service import PropertyService

logger = logging.getLogger(__name__)

router = APIRouter()


def _property_to_dict(prop, similarity: float | None = None) -> dict:
    """将 Property ORM 对象转为字典，用于 LLM 摘要生成"""
    return {
        "title": prop.title,
        "address": prop.address,
        "district": prop.district,
        "price_monthly": float(prop.price_monthly),
        "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "property_type": prop.property_type.value if hasattr(prop.property_type, "value") else str(prop.property_type),
        "description": prop.description,
        "similarity": similarity,
    }


def _to_search_result(prop, similarity: float | None = None) -> PropertySearchResult:
    """将 Property ORM 对象转为 PropertySearchResult"""
    return PropertySearchResult(
        id=prop.id,
        landlord_id=prop.landlord_id,
        title=prop.title,
        description=prop.description,
        address=prop.address,
        district=prop.district,
        price_monthly=prop.price_monthly,
        area_sqm=prop.area_sqm,
        bedrooms=prop.bedrooms,
        bathrooms=prop.bathrooms,
        property_type=prop.property_type,
        status=prop.status,
        latitude=prop.latitude,
        longitude=prop.longitude,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
        images=[
            PropertyImageRead(
                id=img.id,
                property_id=img.property_id,
                filename=img.filename,
                original_name=img.original_name,
                mime_type=img.mime_type,
                file_size=img.file_size,
                sort_order=img.sort_order,
                is_primary=img.is_primary,
                created_at=img.created_at,
            )
            for img in (prop.images or [])
        ],
        similarity=similarity,
    )


@router.post("/parse", response_model=ParseResponse)
async def parse_query(request: ParseRequest) -> ParseResponse:
    """第一步：解析用户自然语言，返回结构化参数 + 完整性报告"""
    try:
        llm = get_llm_service()
        result = await llm.parse_search_query(request.query)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("LLM 解析失败")
        raise HTTPException(status_code=502, detail=f"AI 解析服务暂时不可用: {e}")

    return ParseResponse(
        params=result.get("params", {}),
        completeness=result.get("completeness", {}),
    )


@router.post("/search", response_model=AiSearchResponse)
async def ai_search(
    request: AiSearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AiSearchResponse:
    """第二步：执行检索 + 生成 AI 摘要"""
    property_service = PropertyService(session)

    # 构造语义搜索的 query 文本
    search_query_parts = []
    if request.query:
        search_query_parts.append(request.query)
    if request.district:
        search_query_parts.append(request.district)
    if request.keywords:
        search_query_parts.append(request.keywords)
    search_query = " ".join(search_query_parts) if search_query_parts else None

    # 调用统一检索
    results = await property_service.search(
        query=search_query,
        district=request.district,
        price_min=Decimal(request.price_min) if request.price_min else None,
        price_max=Decimal(request.price_max) if request.price_max else None,
        bedrooms=request.bedrooms,
        property_type=request.property_type,
        limit=request.limit,
    )

    total_count = len(results)
    search_results = [_to_search_result(prop, sim) for prop, sim in results]

    # 生成 AI 摘要（Top 3）
    top3 = results[:3]
    top3_ids = [prop.id for prop, _ in top3]
    top3_dicts = [_property_to_dict(prop, sim) for prop, sim in top3]

    summary = ""
    try:
        llm = get_llm_service()
        summary = await llm.generate_search_summary(
            user_query=request.query,
            top_properties=top3_dicts,
        )
    except RuntimeError:
        # LLM 未配置时静默降级
        if top3_dicts:
            districts = list({p.get("district", "") for p in top3_dicts if p.get("district")})
            district_str = "、".join(districts[:2]) if districts else "附近"
            summary = f"在{district_str}找到 {total_count} 套匹配房源，以下是综合推荐的前 {len(top3_dicts)} 套。"
        else:
            summary = "没有找到匹配的房源，试试放宽条件或换个区域？"
    except Exception:
        logger.exception("AI 摘要生成失败")
        summary = f"共找到 {total_count} 套匹配房源。"

    return AiSearchResponse(
        summary=summary,
        top_ids=top3_ids,
        results=search_results,
        total_count=total_count,
        search_params=request,
    )
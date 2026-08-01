"""搜索建议 API - 基于 UnitType + Institute 两层层结构"""
from typing import Optional

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.institute import Institute
from app.models.unit_type import UnitType

router = APIRouter()


@router.get("/school/{school_id}")
async def get_school_info(
    school_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """获取学校基本信息（公开接口）"""
    result = await db.execute(
        select(Institute.id, Institute.name, Institute.name_cn, Institute.abbreviation,
               Institute.address, Institute.latitude, Institute.longitude)
        .where(Institute.id == school_id, Institute.status == "active")
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="学校不存在")
    return {
        "id": row[0],
        "name": row[1],
        "name_cn": row[2],
        "abbreviation": row[3],
        "address": row[4],
        "latitude": float(row[5]) if row[5] is not None else None,
        "longitude": float(row[6]) if row[6] is not None else None,
    }


@router.get("/suggestions")
async def get_search_suggestions(
    q: Optional[str] = Query(None, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50, description="每类建议的最大数量"),
    db: AsyncSession = Depends(get_db_session),
):
    """获取搜索建议 — 基于 UnitType + Institute JOIN"""
    result = {
        "popular_cities": [],
        "popular_schools": [],
        "matching_cities": [],
        "matching_schools": [],
        "matching_properties": [],
    }

    if not q or not q.strip():
        # 无关键词：热门城市（按 Institute 数量排序）
        city_query = (
            select(
                Institute.district,
                Institute.country,
                func.count(UnitType.id).label("property_count"),
            )
            .join(UnitType, UnitType.institute_id == Institute.id)
            .where(UnitType.status == "available", UnitType.deleted_at.is_(None))
            .group_by(Institute.district, Institute.country)
            .order_by(func.count(UnitType.id).desc())
            .limit(limit)
        )
        city_results = await db.execute(city_query)
        result["popular_cities"] = [
            {
                "type": "city",
                "name": row.district,
                "country": row.country,
                "count": row.property_count,
                "query": {"district": row.district, "country": row.country},
            }
            for row in city_results.all()
        ]

        # 热门学校（按关联户型数量排序）
        school_query = (
            select(
                Institute.id, Institute.name, Institute.name_cn,
                Institute.abbreviation, Institute.address,
                Institute.latitude, Institute.longitude,
                func.count(UnitType.id).label("property_count"),
            )
            .outerjoin(UnitType, UnitType.institute_id == Institute.id)
            .where(
                Institute.status == "active",
                or_(UnitType.status == "available", UnitType.id.is_(None)),
                or_(UnitType.deleted_at.is_(None), UnitType.id.is_(None)),
            )
            .group_by(Institute.id)
            .order_by(func.count(UnitType.id).desc())
            .limit(limit)
        )
        school_results = await db.execute(school_query)
        result["popular_schools"] = [
            {
                "type": "school",
                "id": r.id, "name": r.name, "name_cn": r.name_cn,
                "abbreviation": r.abbreviation, "address": r.address,
                "latitude": float(r.latitude) if r.latitude else None,
                "longitude": float(r.longitude) if r.longitude else None,
                "count": r.property_count, "query": {"school_id": r.id},
            }
            for r in school_results.all()
        ]
    else:
        search_term = f"%{q.strip()}%"

        # 匹配的城市
        city_query = (
            select(
                Institute.district, Institute.country,
                func.count(UnitType.id).label("property_count"),
            )
            .join(UnitType, UnitType.institute_id == Institute.id)
            .where(
                UnitType.status == "available", UnitType.deleted_at.is_(None),
                or_(Institute.district.ilike(search_term), Institute.country.ilike(search_term)),
            )
            .group_by(Institute.district, Institute.country)
            .order_by(func.count(UnitType.id).desc())
            .limit(limit)
        )
        city_results = await db.execute(city_query)
        result["matching_cities"] = [
            {
                "type": "city", "name": r.district, "country": r.country,
                "count": r.property_count,
                "query": {"district": r.district, "country": r.country},
            }
            for r in city_results.all()
        ]

        # 匹配的学校
        school_query = (
            select(
                Institute.id, Institute.name, Institute.name_cn,
                Institute.abbreviation, Institute.address,
                Institute.latitude, Institute.longitude,
                func.count(UnitType.id).label("property_count"),
            )
            .outerjoin(UnitType, UnitType.institute_id == Institute.id)
            .where(
                Institute.status == "active",
                or_(
                    Institute.name.ilike(search_term),
                    Institute.name_cn.ilike(search_term),
                    Institute.abbreviation.ilike(search_term),
                ),
                or_(UnitType.status == "available", UnitType.id.is_(None)),
                or_(UnitType.deleted_at.is_(None), UnitType.id.is_(None)),
            )
            .group_by(Institute.id)
            .order_by(func.count(UnitType.id).desc())
            .limit(limit)
        )
        school_results = await db.execute(school_query)
        result["matching_schools"] = [
            {
                "type": "school", "id": r.id, "name": r.name, "name_cn": r.name_cn,
                "abbreviation": r.abbreviation, "address": r.address,
                "latitude": float(r.latitude) if r.latitude else None,
                "longitude": float(r.longitude) if r.longitude else None,
                "count": r.property_count, "query": {"school_id": r.id},
            }
            for r in school_results.all()
        ]

        # 匹配的户型（名称或地址）
        property_query = (
            select(UnitType)
            .join(Institute, Institute.id == UnitType.institute_id)
            .where(
                UnitType.status == "available",
                UnitType.deleted_at.is_(None),
                or_(
                    UnitType.name.ilike(search_term),
                    Institute.address.ilike(search_term),
                    Institute.name.ilike(search_term),
                ),
            )
            .limit(limit)
        )
        property_results = await db.execute(property_query)
        result["matching_properties"] = [
            {
                "type": "property",
                "id": r.id,
                "title": r.name,
                "district": getattr(getattr(r, 'institute', None), 'district', None),
                "price_monthly": float(r.base_rent) if r.base_rent else None,
                "query": {"property_id": r.id},
            }
            for r in property_results.scalars().all()
        ]

    return result

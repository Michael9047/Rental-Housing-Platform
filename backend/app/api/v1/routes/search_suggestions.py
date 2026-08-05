"""搜索建议 API - 基于 UnitType + Institute 两层层结构"""
from typing import Optional

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.institute import Institute
from app.models.unit_type import UnitType
from app.models.university import University

router = APIRouter()


@router.get("/schools")
async def search_schools(
    q: str = Query(default="", min_length=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
):
    """搜索学校——支持中英文名 + 缩写"""
    term = f"%{q.strip()}%"
    r = await db.execute(
        select(University.id, University.name, University.name_cn,
               University.abbreviation, University.latitude, University.longitude)
        .where(University.is_active == True, or_(
            University.name.ilike(term), University.name_cn.ilike(term),
            University.abbreviation.ilike(term)))
        .order_by(University.sort_order.asc().nulls_last(), University.is_hot.desc(), University.id).limit(limit))
    return [{"id": row[0], "name": row[1], "name_cn": row[2], "abbreviation": row[3],
             "latitude": float(row[4]) if row[4] else None, "longitude": float(row[5]) if row[5] else None}
            for row in r.all()]


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
    country: Optional[str] = Query(None, description="按国家筛选大学"),
    db: AsyncSession = Depends(get_db_session),
):
    """获取搜索建议 — 基于 UnitType + Institute JOIN"""
    result = {
        "popular_cities": [],
        "popular_schools": [],
        "popular_universities": [],
        "matching_cities": [],
        "matching_schools": [],
        "matching_universities": [],
        "matching_properties": [],
    }

    if not q or not q.strip():
        # 无关键词：热门城市（按 city 分组，排除空值）
        city_query = (
            select(
                Institute.city,
                Institute.country,
                func.count(UnitType.id).label("property_count"),
            )
            .join(UnitType, UnitType.institute_id == Institute.id)
            .where(
                UnitType.status == "available", UnitType.deleted_at.is_(None),
                Institute.city.isnot(None), Institute.city != "",
            )
            .group_by(Institute.city, Institute.country)
            .order_by(func.count(UnitType.id).desc())
            .limit(limit * 2)  # 多取一些供前端过滤
        )
        city_results = await db.execute(city_query)
        result["popular_cities"] = [
            {
                "type": "city",
                "name": row.city,
                "country": row.country,
                "count": row.property_count,
                "query": {"city": row.city, "country": row.country},
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

        # 热门大学（全部 active 大学，is_hot 优先）
        uni_conditions = [University.is_active.is_(True)]
        if country:
            uni_conditions.append(University.country == country)
        uni_query = (
            select(University.id, University.name, University.name_cn,
                   University.abbreviation, University.city, University.country,
                   University.latitude, University.longitude)
            .where(*uni_conditions)
            .order_by(University.sort_order.asc().nulls_last(), University.is_hot.desc(), University.name.asc())
            .limit(limit * 3)  # 多取以支持国家筛选
        )
        uni_results = await db.execute(uni_query)
        result["popular_universities"] = [
            {
                "type": "university",
                "id": r.id, "name": r.name, "name_cn": r.name_cn,
                "abbreviation": r.abbreviation, "city": r.city, "country": r.country,
                "latitude": float(r.latitude) if r.latitude else None,
                "longitude": float(r.longitude) if r.longitude else None,
                "query": {"uni_id": r.id},
            }
            for r in uni_results.all()
        ]
    else:
        search_term = f"%{q.strip()}%"

        # 匹配的城市
        city_query = (
            select(
                Institute.city, Institute.country,
                func.count(UnitType.id).label("property_count"),
            )
            .join(UnitType, UnitType.institute_id == Institute.id)
            .where(
                UnitType.status == "available", UnitType.deleted_at.is_(None),
                Institute.city.isnot(None), Institute.city != "",
                or_(Institute.city.ilike(search_term), Institute.country.ilike(search_term)),
            )
            .group_by(Institute.city, Institute.country)
            .order_by(func.count(UnitType.id).desc())
            .limit(limit)
        )
        city_results = await db.execute(city_query)
        result["matching_cities"] = [
            {
                "type": "city", "name": r.city, "country": r.country,
                "count": r.property_count,
                "query": {"city": r.city, "country": r.country},
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

        # 匹配的大学
        uni_conditions = [
            University.is_active.is_(True),
            or_(
                University.name.ilike(search_term),
                University.name_cn.ilike(search_term),
                University.abbreviation.ilike(search_term),
                University.aliases.any(func.lower(q.strip())),
            ),
        ]
        if country:
            uni_conditions.append(University.country == country)
        uni_query = (
            select(University.id, University.name, University.name_cn,
                   University.abbreviation, University.city, University.country,
                   University.latitude, University.longitude)
            .where(*uni_conditions)
            .order_by(University.sort_order.asc().nulls_last(), University.is_hot.desc(), University.name.asc())
            .limit(limit)
        )
        uni_results = await db.execute(uni_query)
        result["matching_universities"] = [
            {
                "type": "university",
                "id": r.id, "name": r.name, "name_cn": r.name_cn,
                "abbreviation": r.abbreviation, "city": r.city, "country": r.country,
                "latitude": float(r.latitude) if r.latitude else None,
                "longitude": float(r.longitude) if r.longitude else None,
                "query": {"uni_id": r.id},
            }
            for r in uni_results.all()
        ]

        # 匹配的公寓（名称或地址）
        property_query = (
            select(Institute)
            .where(
                Institute.status == "active",
                or_(
                    Institute.name.ilike(search_term),
                    Institute.name_cn.ilike(search_term),
                    Institute.address.ilike(search_term),
                ),
            )
            .order_by(Institute.id.desc())
            .limit(limit)
        )
        property_results = await db.execute(property_query)
        result["matching_properties"] = [
            {
                "type": "property",
                "id": r.id,
                "title": r.name_cn or r.name,
                "district": r.district,
                "price_monthly": None,
                "query": {"property_id": r.id},
            }
            for r in property_results.scalars().all()
        ]

    return result

"""搜索建议 API - 提供智能搜索建议"""
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.api.deps import get_db_session
from app.models.property import Property
from app.models.institute import Institute
from typing import Optional

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
    """
    获取搜索建议

    - 无关键词时：返回热门城市、热门学校
    - 有关键词时：返回匹配的城市、学校、房源名称
    """
    result = {
        "popular_cities": [],
        "popular_schools": [],
        "matching_cities": [],
        "matching_schools": [],
        "matching_properties": [],
    }

    if not q or not q.strip():
        # 无关键词：返回热门数据
        # 1. 热门城市（按房源数量排序）
        city_query = (
            select(
                Property.district,
                Property.country,
                func.count(Property.id).label("property_count"),
            )
            .where(Property.status == "available", Property.deleted_at.is_(None))
            .group_by(Property.district, Property.country)
            .order_by(func.count(Property.id).desc())
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

        # 2. 热门学校（按关联房源数量排序）
        school_query = (
            select(
                Institute.id,
                Institute.name,
                Institute.name_cn,
                Institute.abbreviation,
                Institute.address,
                Institute.latitude,
                Institute.longitude,
                func.count(Property.id).label("property_count"),
            )
            .outerjoin(Property, Property.institute_id == Institute.id)
            .where(
                Institute.status == "active",
                or_(Property.status == "available", Property.id.is_(None)),
                or_(Property.deleted_at.is_(None), Property.id.is_(None)),
            )
            .group_by(Institute.id, Institute.name, Institute.name_cn, Institute.abbreviation, Institute.address, Institute.latitude, Institute.longitude)
            .order_by(func.count(Property.id).desc())
            .limit(limit)
        )
        school_results = await db.execute(school_query)
        result["popular_schools"] = [
            {
                "type": "school",
                "id": row.id,
                "name": row.name,
                "name_cn": row.name_cn,
                "abbreviation": row.abbreviation,
                "address": row.address,
                "latitude": float(row.latitude) if row.latitude is not None else None,
                "longitude": float(row.longitude) if row.longitude is not None else None,
                "count": row.property_count,
                "query": {"school_id": row.id},
            }
            for row in school_results.all()
        ]
    else:
        # 有关键词：返回匹配数据
        search_term = f"%{q.strip()}%"

        # 1. 匹配的城市
        city_query = (
            select(
                Property.district,
                Property.country,
                func.count(Property.id).label("property_count"),
            )
            .where(
                Property.status == "available",
                Property.deleted_at.is_(None),
                or_(
                    Property.district.ilike(search_term),
                    Property.country.ilike(search_term),
                ),
            )
            .group_by(Property.district, Property.country)
            .order_by(func.count(Property.id).desc())
            .limit(limit)
        )
        city_results = await db.execute(city_query)
        result["matching_cities"] = [
            {
                "type": "city",
                "name": row.district,
                "country": row.country,
                "count": row.property_count,
                "query": {"district": row.district, "country": row.country},
            }
            for row in city_results.all()
        ]

        # 2. 匹配的学校 —— 支持中英文名 + 缩写多字段搜索
        school_query = (
            select(
                Institute.id,
                Institute.name,
                Institute.name_cn,
                Institute.abbreviation,
                Institute.address,
                Institute.latitude,
                Institute.longitude,
                func.count(Property.id).label("property_count"),
            )
            .outerjoin(Property, Property.institute_id == Institute.id)
            .where(
                Institute.status == "active",
                or_(
                    Institute.name.ilike(search_term),
                    Institute.name_cn.ilike(search_term),
                    Institute.abbreviation.ilike(search_term),
                ),
                or_(Property.status == "available", Property.id.is_(None)),
                or_(Property.deleted_at.is_(None), Property.id.is_(None)),
            )
            .group_by(Institute.id, Institute.name, Institute.name_cn, Institute.abbreviation, Institute.address, Institute.latitude, Institute.longitude)
            .order_by(func.count(Property.id).desc())
            .limit(limit)
        )
        school_results = await db.execute(school_query)
        result["matching_schools"] = [
            {
                "type": "school",
                "id": row.id,
                "name": row.name,
                "name_cn": row.name_cn,
                "abbreviation": row.abbreviation,
                "address": row.address,
                "latitude": float(row.latitude) if row.latitude is not None else None,
                "longitude": float(row.longitude) if row.longitude is not None else None,
                "count": row.property_count,
                "query": {"school_id": row.id},
            }
            for row in school_results.all()
        ]

        # 3. 匹配的房源（标题或地址）
        property_query = (
            select(Property)
            .where(
                Property.status == "available",
                Property.deleted_at.is_(None),
                or_(
                    Property.title.ilike(search_term),
                    Property.address.ilike(search_term),
                ),
            )
            .limit(limit)
        )
        property_results = await db.execute(property_query)
        result["matching_properties"] = [
            {
                "type": "property",
                "id": row.id,
                "title": row.title,
                "district": row.district,
                "price_monthly": float(row.price_monthly) if row.price_monthly else None,
                "query": {"property_id": row.id},
            }
            for row in property_results.scalars().all()
        ]

    return result

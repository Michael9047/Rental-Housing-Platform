"""大学 API — 列出/搜索大学，供前端搜索栏使用"""
from typing import Optional

from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.university import University

router = APIRouter()


@router.get("")
async def list_universities(
    q: Optional[str] = Query(None, description="搜索关键词（名称/缩写/别名）"),
    country: Optional[str] = Query(None, description="国家代码过滤（SG/GB/...）"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
):
    """获取大学列表 — 支持搜索和过滤。

    前端搜索栏键入大学名 → 自动补全 → 选中后按坐标近距搜房。
    """
    stmt = select(
        University.id, University.name, University.name_cn,
        University.abbreviation, University.city, University.country,
        University.latitude, University.longitude,
        University.aliases,
    ).where(University.is_active.is_(True))

    if country:
        stmt = stmt.where(University.country == country.upper())

    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                University.name.ilike(term),
                University.name_cn.ilike(term),
                University.abbreviation.ilike(term),
                # 别名数组 ANY 匹配
                University.aliases.any(func.lower(q.strip())),
            )
        )

    stmt = stmt.order_by(
        University.is_hot.desc(),  # 热门大学排前面
        University.name.asc(),
    ).limit(limit)

    rows = await db.execute(stmt)

    return [
        {
            "id": r.id,
            "name": r.name,
            "name_cn": r.name_cn,
            "abbreviation": r.abbreviation,
            "city": r.city,
            "country": r.country,
            "latitude": float(r.latitude) if r.latitude else None,
            "longitude": float(r.longitude) if r.longitude else None,
        }
        for r in rows.all()
    ]

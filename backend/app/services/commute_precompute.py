"""通勤预计算 —— 公寓导入时异步计算到所有热门大学的公交/步行/驾车时间"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.university import University
from app.models.institute_commute import InstituteCommute
from app.services.commute_service import (
    CommuteDestination,
    calculate_commute_batch_resilient,
)

logger = logging.getLogger(__name__)


async def precompute_for_institute(
    session: AsyncSession,
    institute_id: int,
    lat: float,
    lng: float,
    country_hint: str | None = None,
) -> int:
    """为单个公寓计算到所有热门大学的通勤时间，返回写入条数。"""
    stmt = select(University).where(University.is_hot == True, University.is_active == True)
    result = await session.scalars(stmt)
    all_unis = list(result)

    country = (country_hint or "").upper()
    if country:
        unis = [u for u in all_unis if (u.country or "").upper() == country]
        if not unis:
            unis = all_unis
    else:
        unis = all_unis
    if not unis:
        return 0

    destinations = [
        CommuteDestination(dest_id=u.id, lat=float(u.latitude), lng=float(u.longitude))
        for u in unis
    ]

    try:
        batch = await calculate_commute_batch_resilient(lat, lng, destinations)
    except Exception:
        logger.exception("预计算通勤失败 institute=%s", institute_id)
        return 0

    await session.execute(
        delete(InstituteCommute).where(InstituteCommute.institute_id == institute_id)
    )
    now = datetime.now(timezone.utc)
    count = 0
    for r in batch.results:
        commute = InstituteCommute(
            institute_id=institute_id,
            university_id=r.dest_id,
            transit_min=max(1, round(r.transit_min)) if r.transit_min else None,
            walk_min=max(1, round(r.walk_min)) if r.walk_min else None,
            source=batch.source,
            computed_at=now,
        )
        session.add(commute)
        count += 1
    await session.commit()
    logger.info("预计算完成 institute=%s: %d universities", institute_id, count)
    return count


# 向后兼容旧调用者
async def precompute_for_room(
    session: AsyncSession,
    room_id: int,
    room_lat: float,
    room_lng: float,
) -> int:
    """旧接口：通过 room_id 查找 institute_id 后委托给 institute 级预计算。"""
    from app.models.property import Room
    room = await session.get(Room, room_id)
    if not room or not room.institute_id:
        logger.warning("room=%s 无关联公寓，跳过通勤预计算", room_id)
        return 0
    return await precompute_for_institute(
        session, room.institute_id, room_lat, room_lng,
        country_hint=room.country,
    )


async def precompute_batch(
    session: AsyncSession,
    rooms: list[tuple[int, float, float]],
    max_concurrent: int = 3,
) -> int:
    """批量预计算（限并发），支持按 room 或 institute 粒度调用。"""
    total = 0
    sem = asyncio.Semaphore(max_concurrent)

    async def _one(rid: int, lat: float, lng: float):
        nonlocal total
        async with sem:
            c = await precompute_for_room(session, rid, lat, lng)
            total += c

    tasks = [_one(rid, lat, lng) for rid, lat, lng in rooms if lat and lng]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("批量预计算完成: %d rooms → %d records", len(rooms), total)
    return total

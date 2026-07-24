"""通勤预计算 —— 房源导入时异步计算到所有热门大学的公交/步行/驾车时间"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.university import University
from app.models.room_commute import RoomCommute
from app.services.commute_service import (
    CommuteDestination,
    calculate_commute_batch_resilient,
)

logger = logging.getLogger(__name__)


async def precompute_for_room(
    session: AsyncSession,
    room_id: int,
    room_lat: float,
    room_lng: float,
) -> int:
    """为单个房源计算到所有热门大学的通勤时间，返回写入条数。"""
    # 查热门大学（只算同一国家的，不跨洲）
    stmt = select(University).where(University.is_hot == True, University.is_active == True)
    result = await session.scalars(stmt)
    all_unis = list(result)

    # 从 room 推断国家
    from app.models.property import Room
    room = await session.get(Room, room_id)
    room_country = None
    if room and room.country:
        room_country = room.country.upper()
    elif room and room.district and "新加坡" in room.district:
        room_country = "SG"
    elif room and room.district and ("伦敦" in room.district or "London" in room.district):
        room_country = "GB"

    if room_country:
        unis = [u for u in all_unis if (u.country or "").upper() == room_country]
        if not unis:
            unis = all_unis  # 兜底：全算
    else:
        unis = all_unis
    if not unis:
        return 0

    # 构建目的地列表
    destinations = [
        CommuteDestination(dest_id=u.id, lat=float(u.latitude), lng=float(u.longitude))
        for u in unis
    ]

    # 调批量引擎
    try:
        batch = await calculate_commute_batch_resilient(room_lat, room_lng, destinations)
    except Exception:
        logger.exception("预计算通勤失败 room=%s", room_id)
        return 0

    # 写入（先删旧数据再插）
    await session.execute(delete(RoomCommute).where(RoomCommute.room_id == room_id))
    now = datetime.now(timezone.utc)
    count = 0
    for r in batch.results:
        commute = RoomCommute(
            room_id=room_id,
            university_id=r.dest_id,
            transit_min=max(1, round(r.transit_min)) if r.transit_min else None,
            walk_min=max(1, round(r.walk_min)) if r.walk_min else None,
            source=batch.source,
            computed_at=now,
        )
        session.add(commute)
        count += 1
    await session.commit()
    logger.info("预计算完成 room=%s: %d universities", room_id, count)
    return count


async def precompute_batch(
    session: AsyncSession,
    rooms: list[tuple[int, float, float]],  # [(room_id, lat, lng), ...]
    max_concurrent: int = 3,
) -> int:
    """批量预计算（限并发，避免打爆 API）。"""
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

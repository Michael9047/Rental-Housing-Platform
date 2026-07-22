"""房间流转记录路由"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.room_transfer import RoomTransfer
from app.schemas.tenant_order import RoomTransferRead

router = APIRouter(tags=["room-transfers"])


@router.get("/rooms/{room_id}/transfers", response_model=list[RoomTransferRead])
async def list_transfers(room_id: int, session: AsyncSession = Depends(get_db_session)):
    result = await session.scalars(
        select(RoomTransfer).where(RoomTransfer.room_id == room_id).order_by(RoomTransfer.created_at.desc())
    )
    return list(result)

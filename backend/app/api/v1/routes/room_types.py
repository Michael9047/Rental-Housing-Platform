"""房型 CRUD 路由 — 挂载在 /properties/{property_id}/room-types 下"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.schemas.room_type import RoomTypeCreate, RoomTypeRead, RoomTypeUpdate
from app.services.room_type_service import RoomTypeService

router = APIRouter()


@router.get("/{property_id}/room-types", response_model=list[RoomTypeRead])
async def list_room_types(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """获取某个楼栋下的所有房型（公开）"""
    return await RoomTypeService(session).list_by_property(property_id)


@router.post("/{property_id}/room-types", response_model=RoomTypeRead, status_code=status.HTTP_201_CREATED)
async def create_room_type(
    property_id: int,
    room_type_in: RoomTypeCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """为楼栋添加房型"""
    return await RoomTypeService(session).create(property_id, room_type_in, current_user.id)


@router.get("/{property_id}/room-types/{room_type_id}", response_model=RoomTypeRead)
async def get_room_type(
    property_id: int,
    room_type_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """获取单个房型详情"""
    rt = await RoomTypeService(session).get(property_id, room_type_id)
    if not rt:
        raise HTTPException(status_code=404, detail="房型不存在")
    return rt


@router.patch("/{property_id}/room-types/{room_type_id}", response_model=RoomTypeRead)
async def update_room_type(
    property_id: int,
    room_type_id: int,
    room_type_in: RoomTypeUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """更新房型信息"""
    rt = await RoomTypeService(session).update(property_id, room_type_id, room_type_in, current_user.id)
    if not rt:
        raise HTTPException(status_code=404, detail="房型不存在")
    return rt


@router.delete("/{property_id}/room-types/{room_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_type(
    property_id: int,
    room_type_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """删除房型"""
    deleted = await RoomTypeService(session).delete(property_id, room_type_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="房型不存在")

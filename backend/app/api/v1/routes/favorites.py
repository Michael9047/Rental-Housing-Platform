"""收藏路由 - 租客收藏/取消收藏房源。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_tenant
from app.models.user import User
from app.schemas.user_favorite import FavoriteCreate, FavoriteRead
from app.services.favorite_service import FavoriteService

router = APIRouter()


@router.post("", response_model=FavoriteRead, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    fav_in: FavoriteCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> FavoriteRead:
    """新增收藏 - 租客收藏房源。"""
    svc = FavoriteService(session)
    fav = await svc.add(current_user.id, fav_in.property_id)
    return fav


@router.get("", response_model=list[FavoriteRead])
async def list_favorites(
    property_id: int | None = Query(default=None, description="按房源ID筛选单条收藏"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[FavoriteRead]:
    """获取当前用户的收藏列表，可选按 property_id 筛选。"""
    svc = FavoriteService(session)
    if property_id is not None:
        fav = await svc.get_by_property(current_user.id, property_id)
        return [fav] if fav else []
    return await svc.list_by_user(current_user.id)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> None:
    """取消收藏 - 按房源ID删除收藏记录。"""
    svc = FavoriteService(session)
    removed = await svc.remove(current_user.id, property_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found for this property",
        )

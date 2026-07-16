"""收藏服务 - 增删查。"""
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_favorite import UserFavorite


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: int, property_id: int) -> UserFavorite:
        """新增收藏，已存在则直接返回。"""
        existing = await self.get_by_property(user_id, property_id)
        if existing:
            return existing

        fav = UserFavorite(user_id=user_id, property_id=property_id)
        self.session.add(fav)
        await self.session.commit()
        await self.session.refresh(fav)
        return fav

    async def remove(self, user_id: int, property_id: int) -> bool:
        """删除收藏，返回是否成功删除。"""
        fav = await self.get_by_property(user_id, property_id)
        if not fav:
            return False
        await self.session.delete(fav)
        await self.session.commit()
        return True

    async def is_favorited(self, user_id: int, property_id: int) -> bool:
        """检查是否已收藏。"""
        fav = await self.get_by_property(user_id, property_id)
        return fav is not None

    async def list_by_user(self, user_id: int) -> list[UserFavorite]:
        """列出用户所有收藏，按时间倒序。"""
        stmt = (
            select(UserFavorite)
            .where(UserFavorite.user_id == user_id)
            .order_by(UserFavorite.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def get_by_property(
        self, user_id: int, property_id: int
    ) -> UserFavorite | None:
        stmt = select(UserFavorite).where(
            and_(
                UserFavorite.user_id == user_id,
                UserFavorite.property_id == property_id,
            )
        )
        result = await self.session.scalars(stmt)
        return result.first()

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_in: UserCreate) -> User:
        user = User(**user_in.model_dump())
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        stmt = select(User).where(
            or_(
                User.username == identifier,
                User.email == identifier,
            )
        )
        result = await self.session.scalars(stmt)
        return result.first()

    async def list(self, *, skip: int = 0, limit: int = 20) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.scalars(stmt)
        return list(result)

    async def update(self, user_id: int, user_in: UserUpdate) -> User | None:
        user = await self.get(user_id)
        if not user:
            return None

        for key, value in user_in.model_dump(exclude_unset=True).items():
            setattr(user, key, value)

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: int) -> bool:
        user = await self.get(user_id)
        if not user:
            return False

        await self.session.delete(user)
        await self.session.commit()
        return True

from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token as encode_access_token
from app.core.security import decode_access_token, hash_password, verify_password
from app.models.user import User, UserStatus
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserCreate
from app.services.user_service import UserService
from app.services.wechat_service import WeChatService


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserService(session)

    async def register_user(self, register_in: RegisterRequest) -> User:
        user_in = UserCreate(
            username=register_in.username,
            password_hash=hash_password(register_in.password),
            phone=register_in.phone,
            email=register_in.email,
            role=register_in.role,
        )
        return await self.users.create(user_in)

    async def authenticate(self, identifier: str, password: str) -> User | None:
        user = await self.users.get_by_username_or_email(identifier)
        if not user or user.status != UserStatus.active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_access_token(self, user: User) -> str:
        return encode_access_token(subject=str(user.id))

    async def get_current_user_from_token(self, token: str) -> User | None:
        try:
            payload = decode_access_token(token)
            subject = payload.get("sub")
            user_id = int(subject)
        except (InvalidTokenError, TypeError, ValueError):
            return None

        user = await self.users.get(user_id)
        if not user or user.status != UserStatus.active:
            return None
        return user

    async def wechat_login(self, code: str) -> tuple[User, bool]:
        """WeChat Mini Program login: exchange code for openid, find or create user, return JWT-ready user."""
        wechat = WeChatService()
        session_data = await wechat.jscode2session(code)

        # Look up existing user by openid
        stmt = select(User).where(User.wechat_openid == session_data.openid)
        result = await self.session.scalars(stmt)
        user = result.first()

        is_new = False
        if not user:
            is_new = True
            user_in = UserCreate(
                username=f"wx_{session_data.openid[-12:]}",
                password_hash=hash_password(session_data.openid),
                role="tenant",
            )
            user = await self.users.create(user_in)
            user.wechat_openid = session_data.openid
            await self.session.commit()
            await self.session.refresh(user)

        return user, is_new

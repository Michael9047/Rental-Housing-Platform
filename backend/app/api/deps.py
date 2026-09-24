import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# 游客模式：不强制要求 token
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    user = await AuthService(session).get_current_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(
    token: str | None = Depends(oauth2_scheme_optional),
    session: AsyncSession = Depends(get_db_session),
) -> User | None:
    """返回当前用户，未登录则返回 None（不抛 401）。"""
    if token is None:
        return None
    return await AuthService(session).get_current_user_from_token(token)


# 别名：chat.py 等模块引用的旧名称
get_current_user_optional = get_optional_user


from fastapi import Request, Response

async def _get_or_create_guest_user(
    session: AsyncSession,
    request: Request | None = None,
    response: Response | None = None,
) -> User:
    """为游客创建或恢复临时用户。

    有 Cookie guest_id → 查 DB 恢复；无 → 新建并 Set-Cookie。
    保证同一访客跨请求共享身份，guest 创建的 session 后续可正常访问。
    """
    # 1. 尝试从 Cookie 恢复已有的 guest
    if request is not None:
        guest_id_str = request.cookies.get("guest_id")
        if guest_id_str:
            try:
                guest_id = int(guest_id_str)
                existing = await session.get(User, guest_id)
                if existing is not None and existing.username.startswith("guest_"):
                    return existing
            except (ValueError, TypeError):
                pass

    # 2. 新建 guest
    guest_username = f"guest_{uuid.uuid4().hex[:16]}"
    guest = User(username=guest_username)
    session.add(guest)
    await session.commit()
    await session.refresh(guest)

    # 3. 设置 Cookie 保持身份
    if response is not None:
        response.set_cookie(
            key="guest_id",
            value=str(guest.id),
            max_age=86400 * 30,
            httponly=True,
            samesite="lax",
        )
    return guest


async def require_landlord(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.landlord, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Landlord or admin role required",
        )
    return current_user


async def require_tenant(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.tenant, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant or admin role required",
        )
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def require_maintenance(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.maintenance_worker, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maintenance worker or admin role required",
        )
    return current_user

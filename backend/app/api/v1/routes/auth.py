from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService

router = APIRouter()


@router.post("/register", response_model=CurrentUserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    register_in: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUserResponse:
    try:
        user = await AuthService(session).register_user(register_in)
        await AuditService(session).create_log(
            user_id=user.id,
            action="user_register",
            resource_type="user",
            resource_id=user.id,
            ip_address=request.client.host if request.client else None,
        )
        return user
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username, email, or phone already exists",
        ) from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    login_in: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    auth_service = AuthService(session)
    user = await auth_service.authenticate(login_in.identifier, login_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await AuditService(session).create_log(
        user_id=user.id,
        action="user_login",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(access_token=auth_service.create_access_token(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request) -> TokenResponse:
    """Issue a new access token using a refresh token from Authorization header."""
    from app.core.security_audit import refresh_access_token

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required in Authorization header",
        )
    token = auth_header[7:]

    try:
        tokens = refresh_access_token(token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    return TokenResponse(
        access_token=tokens["access_token"],
        token_type=tokens["token_type"],
    )


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return current_user
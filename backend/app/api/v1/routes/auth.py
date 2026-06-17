from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=CurrentUserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    register_in: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUserResponse:
    try:
        return await AuthService(session).register_user(register_in)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username, email, or phone already exists",
        ) from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    login_in: LoginRequest,
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

    return TokenResponse(access_token=auth_service.create_access_token(user))


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return current_user

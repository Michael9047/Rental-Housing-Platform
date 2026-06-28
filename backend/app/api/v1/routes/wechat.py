from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import get_settings
from app.models.user import User
from app.schemas.auth import (
    WeChatConfigResponse,
    WeChatLoginRequest,
    WeChatLoginResponse,
    WeChatPhoneRequest,
)
from app.services.auth_service import AuthService
from app.services.wechat_service import WeChatService

router = APIRouter()


@router.post("/auth/wechat/login", response_model=WeChatLoginResponse)
async def wechat_login(
    login_in: WeChatLoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> WeChatLoginResponse:
    """WeChat Mini Program login: exchange wx.login() code for JWT."""
    auth_service = AuthService(session)
    try:
        user, is_new = await auth_service.wechat_login(login_in.code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return WeChatLoginResponse(
        access_token=auth_service.create_access_token(user),
        is_new_user=is_new,
        user=user,
    )


@router.post("/auth/wechat/phone")
async def wechat_phone_bind(
    phone_in: WeChatPhoneRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Bind WeChat phone number to the current user account."""
    wechat = WeChatService()
    access_token = await wechat.get_access_token()
    import httpx
    phone_url = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
    params = {"access_token": access_token}
    body = {"code": phone_in.code}

    async with httpx.AsyncClient() as client:
        resp = await client.post(phone_url, params=params, json=body)
        resp.raise_for_status()
        data = resp.json()

    if data.get("errcode", 0) != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phone binding failed: {data.get('errmsg', 'unknown error')}",
        )

    phone_info = data.get("phone_info", {})
    phone_number = phone_info.get("pure_phone_number") or phone_info.get("phone_number")

    if phone_number:
        current_user.phone = phone_number
        await session.commit()
        await session.refresh(current_user)

    return {"phone": phone_number}


@router.get("/wechat/config", response_model=WeChatConfigResponse)
async def wechat_config() -> WeChatConfigResponse:
    """Get WeChat Mini Program configuration for frontend."""
    settings = get_settings()
    return WeChatConfigResponse(appid=settings.wechat_appid)

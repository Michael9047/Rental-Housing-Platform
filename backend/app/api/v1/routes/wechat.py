import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import get_settings
from app.core.security import (
    consume_wechat_qr_code,
    store_wechat_qr_code,
    store_wechat_qr_state,
    verify_and_consume_wechat_qr_state,
)
from app.models.user import User
from app.schemas.auth import (
    WeChatConfigResponse,
    WeChatLoginRequest,
    WeChatLoginResponse,
    WeChatPhoneRequest,
    WeChatQrLoginRequest,
    WeChatQrStatusResponse,
    WeChatQrUrlResponse,
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
        data = await resp.json()

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


# ── 微信开放平台扫码登录（Web OAuth）────────────────


@router.get("/auth/wechat/qr-url", response_model=WeChatQrUrlResponse)
async def get_wechat_qr_url() -> WeChatQrUrlResponse:
    """生成微信扫码登录 URL 与 state token"""
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    await store_wechat_qr_state(state, ttl=300)

    wechat = WeChatService()
    qr_url = wechat.get_qr_connect_url(settings.wechat_open_redirect_uri, state)

    return WeChatQrUrlResponse(qr_url=qr_url, state=state, expires_in=300)


@router.post("/auth/wechat/qr-login", response_model=WeChatLoginResponse)
async def wechat_qr_login(
    login_in: WeChatQrLoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> WeChatLoginResponse:
    """扫码回调：校验 state + code → openid → JWT"""
    if not await verify_and_consume_wechat_qr_state(login_in.state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效或已过期的 state token",
        )

    auth_service = AuthService(session)
    try:
        user, is_new = await auth_service.wechat_qr_login(login_in.code)
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


@router.get("/auth/wechat/qr-status/{state}", response_model=WeChatQrStatusResponse)
async def get_wechat_qr_status(
    state: str,
    session: AsyncSession = Depends(get_db_session),
) -> WeChatQrStatusResponse:
    """前端轮询扫码状态：pending / scanned / expired"""
    code = await consume_wechat_qr_code(state)
    if code:
        # 已扫码，直接返回登录结果
        auth_service = AuthService(session)
        try:
            user, is_new = await auth_service.wechat_qr_login(code)
        except ValueError:
            return WeChatQrStatusResponse(status="expired")
        return WeChatQrStatusResponse(
            status="scanned",
            access_token=auth_service.create_access_token(user),
            token_type="bearer",
            is_new_user=is_new,
            user=user,
        )

    # 检查 state 是否还存在（未过期）
    r = await _redis_check(f"wechat_qr_state:{state}")
    if r:
        return WeChatQrStatusResponse(status="pending")
    return WeChatQrStatusResponse(status="expired")


@router.get("/auth/wechat/callback")
async def wechat_qr_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """微信 OAuth 回调端点 — 暂存 code 并重定向到前端回调页"""
    from urllib.parse import urlencode

    settings = get_settings()
    # 校验 state 有效性
    if not await verify_and_consume_wechat_qr_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效或已过期的 state token",
        )

    # 暂存 code 供轮询消费
    await store_wechat_qr_code(state, code, ttl=120)

    # 重定向到前端回调页
    frontend_url = settings.frontend_url.rstrip("/")
    params = urlencode({"code": code, "state": state})
    return RedirectResponse(url=f"{frontend_url}/auth/wechat/callback?{params}")


async def _redis_check(key: str) -> bool:
    """检查 Redis key 是否存在"""
    from redis.asyncio import Redis as _Redis
    try:
        r = _Redis.from_url(get_settings().redis_url)
        exists = await r.exists(key)
        await r.close()
        return bool(exists)
    except Exception:
        return False

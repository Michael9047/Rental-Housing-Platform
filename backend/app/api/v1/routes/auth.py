import secrets as _secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import get_settings
from app.core.security import (
    check_sms_rate_limit,
    consume_reset_token,
    hash_password,
    store_reset_token,
    store_sms_code,
    verify_and_consume_sms_code,
)
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendSmsCodeRequest,
    TokenResponse,
    VerifySmsCodeRequest,
    VerifySmsCodeResponse,
)
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.services.email_service import EmailService
from app.services.sms_service import SmsService

router = APIRouter()


# 注册
@router.post("/register", response_model=CurrentUserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    register_in: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUserResponse:
    # 如果提供了手机号，必须验证 SMS 码
    if register_in.phone:
        if not register_in.sms_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号注册需要提供短信验证码",
            )
        verified = await verify_and_consume_sms_code(register_in.phone, register_in.sms_code)
        if not verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误或已过期",
            )

    try:
        user = await AuthService(session).register_user(register_in)
        # phone_verified pending future DB migration
        if register_in.phone and register_in.sms_code:
            await session.commit()
            await session.refresh(user)

        await AuditService(session).create_log(
            user_id=user.id,
            action="user_register",
            resource_type="user",
            resource_id=user.id,
            ip_address=request.client.host if request.client else None,
        )

        # 发送欢迎邮件
        try:
            from app.tasks.notification_tasks import send_email_notification
            send_email_notification.delay(
                user_id=user.id,
                subject="欢迎加入租房平台！",
                html_body=f"<h3>欢迎，{user.username}！</h3><p>感谢您注册我们的租房平台。现在可以开始浏览房源了。</p>",
            )
        except Exception:
            pass

        return user
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username, email, or phone already exists",
        ) from exc


# 登陆
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


# 刷新 Token
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


# ── SMS 验证码 ──────────────────────────────────────────────


@router.post("/send-sms-code")
async def send_sms_code(
    req: SendSmsCodeRequest,
) -> dict:
    """发送短信验证码"""
    # 频率检查：60 秒内只能发一次
    allowed = await check_sms_rate_limit(req.phone)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请等待 60 秒后再获取验证码",
        )

    # 生成 6 位验证码
    code = str(_secrets.randbelow(1000000)).zfill(6)

    # 存储到 Redis（5 分钟过期）
    await store_sms_code(req.phone, code, ttl=300)

    # 发送短信
    sms = SmsService()
    result = await sms.send(req.phone, template_param={"code": code, "min": "5"})

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"短信发送失败: {result.get('error', '未知错误')}",
        )

    return {"detail": "验证码已发送"}


@router.post("/verify-sms-code", response_model=VerifySmsCodeResponse)
async def verify_sms_code(
    req: VerifySmsCodeRequest,
) -> VerifySmsCodeResponse:
    """验证短信验证码"""
    verified = await verify_and_consume_sms_code(req.phone, req.code)
    return VerifySmsCodeResponse(verified=verified)


# ── 密码重置 ──────────────────────────────────────────────────


@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """忘记密码 - 发送重置链接到邮箱"""
    # 查找用户
    stmt = select(User).where(User.email == req.email)
    result = await session.scalars(stmt)
    user = result.first()

    # 无论用户是否存在都返回成功，防止邮箱枚举
    if not user:
        return {"detail": "如果该邮箱已注册，重置链接已发送"}

    # 生成重置 token 并存入 Redis（30 分钟）
    token = _secrets.token_urlsafe(32)
    await store_reset_token(user.id, token, ttl=1800)

    # 发送重置邮件
    settings = get_settings()
    reset_link = f"{settings.frontend_url}/reset-password?token={token}"
    email_svc = EmailService()
    try:
        await email_svc.send(
            to_email=user.email,
            subject="密码重置请求",
            html_body=(
                f"<h3>密码重置</h3>"
                f"<p>点击以下链接重置密码（有效期 30 分钟）：</p>"
                f"<p><a href='{reset_link}'>{reset_link}</a></p>"
                f"<p>如果您没有请求重置密码，请忽略此邮件。</p>"
            ),
        )
    except Exception:
        pass  # 不暴露邮件发送失败给调用方

    return {"detail": "如果该邮箱已注册，重置链接已发送"}


@router.post("/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """重置密码"""
    # 验证 token
    user_id = await consume_reset_token(req.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置链接无效或已过期",
        )

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 更新密码
    user.password_hash = hash_password(req.new_password)
    await session.commit()

    return {"detail": "密码已重置成功"}

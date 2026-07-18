from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole, UserStatus


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    sms_code: str | None = Field(default=None, max_length=6)
    email: EmailStr | None = None
    role: UserRole = UserRole.tenant


class SendSmsCodeRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=32)


class VerifySmsCodeRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=32)
    code: str = Field(min_length=6, max_length=6)


class VerifySmsCodeResponse(BaseModel):
    verified: bool


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @property
    def identifier(self) -> str:
        return self.username_or_email


class PhoneLoginRequest(BaseModel):
    """手机号 + 短信验证码登录请求"""
    phone: str = Field(min_length=11, max_length=32)
    sms_code: str = Field(min_length=6, max_length=6)


class PhoneLoginResponse(BaseModel):
    """手机号登录响应：已注册用户直接返回 token，新用户返回 is_new=True"""
    access_token: str | None = None
    token_type: str = "bearer"
    is_new_user: bool = False
    phone: str


class PhoneRegisterRequest(BaseModel):
    """新用户手机号注册：完成短信验证后设置用户名和密码。

    短信验证已通过 /auth/phone-login 完成（验证状态暂存 Redis），
    此处仅需提供注册信息，无需再次提交验证码。
    """
    phone: str = Field(min_length=11, max_length=32)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.tenant


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WeChatLoginRequest(BaseModel):
    code: str = Field(min_length=1, description="wx.login() returned code")


class WeChatPhoneRequest(BaseModel):
    code: str = Field(min_length=1, description="wx.getPhoneNumber() returned code")
    iv: str | None = Field(default=None, description="Encrypted data IV")
    encrypted_data: str | None = Field(default=None, description="Encrypted data")


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    phone: str | None = None
    wechat_openid: str | None = None
    email: EmailStr | None = None
    # email_verified/phone_verified pending future DB migration
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class WeChatLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool = False
    user: CurrentUserResponse


class WeChatConfigResponse(BaseModel):
    appid: str

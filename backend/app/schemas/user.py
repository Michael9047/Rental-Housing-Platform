from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    wechat_openid: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    role: UserRole = UserRole.tenant
    status: UserStatus = UserStatus.active


class UserCreate(UserBase):
    password_hash: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=100)
    password_hash: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    wechat_openid: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    role: UserRole | None = None
    status: UserStatus | None = None


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

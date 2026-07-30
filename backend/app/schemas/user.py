from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    wechat_openid: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    # email_verified/phone_verified columns pending future DB migration
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
    """学生档案更新 — 所有字段可选"""
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    preferred_name: str | None = Field(default=None, max_length=100)
    enrollment_level: str | None = Field(default=None, max_length=20)
    enrollment_class: str | None = Field(default=None, max_length=30)
    enrollment_term: str | None = Field(default=None, max_length=20)
    school_name: str | None = Field(default=None, max_length=200)
    major: str | None = Field(default=None, max_length=200)
    student_classification: str | None = Field(default=None, max_length=30)
    is_international: bool | None = None
    visa_type: str | None = Field(default=None, max_length=50)
    visa_expiry: str | None = None  # ISO date string
    nationality: str | None = Field(default=None, max_length=100)
    citizenship_country: str | None = Field(default=None, max_length=100)
    disability_needs: str | None = None
    dietary_needs: str | None = None
    gender_identity: str | None = Field(default=None, max_length=30)


class UserProfileRead(UserBase):
    """完整学生档案"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    preferred_name: str | None = None
    enrollment_level: str | None = None
    enrollment_class: str | None = None
    enrollment_term: str | None = None
    school_name: str | None = None
    major: str | None = None
    student_classification: str | None = None
    is_international: bool = False
    visa_type: str | None = None
    visa_expiry: str | None = None
    nationality: str | None = None
    citizenship_country: str | None = None
    disability_needs: str | None = None
    dietary_needs: str | None = None
    gender_identity: str | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole, UserStatus


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    role: UserRole = UserRole.tenant


class LoginRequest(BaseModel):
    username_or_email: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_identifier(self) -> "LoginRequest":
        if not (self.username_or_email or self.username or self.email):
            raise ValueError("username_or_email, username, or email is required")
        return self

    @property
    def identifier(self) -> str:
        return self.username_or_email or self.username or str(self.email)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    phone: str | None = None
    email: EmailStr | None = None
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime

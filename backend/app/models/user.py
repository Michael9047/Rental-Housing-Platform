"""用户模型 - 租客、房东、BD经理、系统管理员"""
import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class UserRole(str, enum.Enum):
    tenant = "tenant"
    landlord = "landlord"
    bd_manager = "bd_manager"
    maintenance_worker = "maintenance_worker"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    deleted = "deleted"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    wechat_openid: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.tenant,
        nullable=False,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        default=UserStatus.active,
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(default=False, nullable=False)

    properties: Mapped[list["Property"]] = relationship(
        back_populates="landlord",
        cascade="all, delete-orphan",
    )

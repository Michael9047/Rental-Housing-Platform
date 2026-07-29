"""用户模型 - 租客、房东、BD经理、系统管理员"""
import enum

from sqlalchemy import Boolean, Date, Enum, String, Text
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
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="landlord",
        cascade="all, delete-orphan",
    )

    # ── 学生档案（StarRez 对照）──
    enrollment_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # undergraduate / graduate / phd / language / other
    enrollment_class: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 大一～大四 / 研一～研三
    enrollment_term: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Fall / Spring / Summer
    school_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    major: Mapped[str | None] = mapped_column(String(200), nullable=True)
    student_classification: Mapped[str | None] = mapped_column(String(30), nullable=True)  # freshman / returning / transfer / exchange
    is_international: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visa_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    visa_expiry: Mapped[str | None] = mapped_column(Date, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    citizenship_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    disability_needs: Mapped[str | None] = mapped_column(Text, nullable=True)
    dietary_needs: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender_identity: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 用于室友匹配
    preferred_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

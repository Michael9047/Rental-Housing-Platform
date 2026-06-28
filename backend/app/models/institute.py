"""公寓管理机构模型 - 大型公寓管理机构，由BD经理代录入，非直接系统用户。"""
import enum
from sqlalchemy import Boolean, Enum, ForeignKey, String, Text as SAText
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins import TimestampMixin
from app.db.session import Base


class InstituteStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"


class Institute(TimestampMixin, Base):
    __tablename__ = "institutes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(SAText)
    has_api: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_config: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[InstituteStatus] = mapped_column(
        Enum(InstituteStatus, name="institute_status"),
        default=InstituteStatus.pending,
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])
    properties: Mapped[list["Property"]] = relationship(
        back_populates="institute", lazy="selectin"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="institute", lazy="selectin"
    )

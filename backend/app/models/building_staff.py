"""公寓工作人员模型"""
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class BuildingStaff(TimestampMixin, Base):
    """公寓工作人员"""
    __tablename__ = "building_staff"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="staff", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    institute: Mapped["Institute"] = relationship(back_populates="staff")

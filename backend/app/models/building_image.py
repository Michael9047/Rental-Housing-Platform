"""公寓图片模型"""
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class BuildingImage(TimestampMixin, Base):
    """公寓实拍图"""
    __tablename__ = "building_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    institute: Mapped["Institute"] = relationship(back_populates="images")

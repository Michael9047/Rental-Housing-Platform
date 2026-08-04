"""用户收藏模型 — 租客收藏户型"""
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class UserFavorite(TimestampMixin, Base):
    __tablename__ = "user_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "unit_type_id", name="uq_user_favorite_unit_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    unit_type_id: Mapped[int] = mapped_column(
        ForeignKey("unit_types.id", ondelete="CASCADE"), index=True, nullable=False
    )

    user: Mapped["User"] = relationship()
    unit_type: Mapped["UnitType"] = relationship()

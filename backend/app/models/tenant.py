"""房客信息模型"""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import TimestampMixin
from app.db.session import Base


class Tenant(TimestampMixin, Base):
    """房客信息"""
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)

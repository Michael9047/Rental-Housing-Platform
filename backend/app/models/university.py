"""大学模型 — 学校坐标表，用于「校附近找房」硬筛选"""
from __future__ import annotations

from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class University(Base):
    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_cn: Mapped[str | None] = mapped_column(String(200), nullable=True)
    abbreviation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False)

"""房间通勤预计算表 —— 房源→热门大学 公交/步行/驾车时间"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RoomCommute(Base):
    __tablename__ = "room_commutes"

    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), primary_key=True)
    transit_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    walk_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drive_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

<<<<<<< HEAD
<<<<<<<< HEAD:backend/app/models/institute_commute.py
"""公寓通勤预计算表 —— 公寓→大学 公交/步行/驾车时间"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
=======
"""公寓通勤预计算表 — 公寓→热门大学 公交/步行/驾车时间"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
>>>>>>> merge/pr33-pr35
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class InstituteCommute(Base):
    __tablename__ = "institute_commutes"

<<<<<<< HEAD
    institute_id: Mapped[int] = mapped_column(ForeignKey("institutes.id", ondelete="CASCADE"), primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), primary_key=True)
=======
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), primary_key=True
    )
    university_id: Mapped[int] = mapped_column(
        ForeignKey("universities.id", ondelete="CASCADE"), primary_key=True
    )
>>>>>>> merge/pr33-pr35
    transit_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    walk_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drive_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
<<<<<<< HEAD
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
========
"""已废弃 — RoomCommute 表已删除，已被 InstituteCommute 替代。保留兼容导入。"""
from app.models._compat import RoomCommute
>>>>>>>> merge/pr33-pr35:backend/app/models/room_commute.py
=======
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
>>>>>>> merge/pr33-pr35

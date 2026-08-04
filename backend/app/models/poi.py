"""公寓周边设施模型 — 关联楼栋而非户型"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text as SAText
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class InstitutePOI(TimestampMixin, Base):
    __tablename__ = "institute_pois"

    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), primary_key=True
    )
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), unique=True, index=True
    )
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    poi_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    # 地图小卡片预生成数据：6 大类 POI（含 lat/lng），创建公寓时 Celery 异步生成
    map_poi_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 安全评分数据：data.gov.sg / Police.uk 街区犯罪数据
    safety_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    institute: Mapped["Institute"] = relationship()


# 向后兼容别名
PropertyPOI = InstitutePOI

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text as SAText
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class PropertyPOI(TimestampMixin, Base):
    __tablename__ = "property_pois"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), unique=True, index=True
    )
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    poi_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    # 地图小卡片预生成数据：6 大类 POI（含 lat/lng），创建房源时 Celery 异步生成
    map_poi_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    property: Mapped["Room"] = relationship()
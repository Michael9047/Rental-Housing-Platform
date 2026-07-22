"""PMS 对接配置模型 — 存储各公寓 PMS 的 API 凭证、映射规则与同步状态"""
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class PMSType(str, enum.Enum):
    """支持的 PMS 系统类型"""
    starrez = "starrez"
    mews = "mews"
    cloudbeds = "cloudbeds"
    ota_xml = "ota_xml"
    custom = "custom"


class PMSSyncStatus(str, enum.Enum):
    """PMS 同步状态"""
    idle = "idle"               # 未在同步
    syncing = "syncing"         # 同步进行中
    success = "success"         # 上次同步成功
    failed = "failed"           # 上次同步失败
    pending_review = "pending_review"  # 有待人工确认的映射


class PMSConnection(TimestampMixin, Base):
    """PMS 对接配置 —— 每条记录代表一个公寓的 PMS 对接"""

    __tablename__ = "pms_connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    institute_id: Mapped[int] = mapped_column(
        ForeignKey("institutes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # ── PMS 基本配置 ──
    pms_type: Mapped[PMSType] = mapped_column(
        Enum(PMSType, name="pms_type"), nullable=False,
    )
    label: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="人工可读标签，如 'Unite Manchester'"
    )
    base_url: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="PMS API 地址，mock:// 前缀表示 Mock 模式"
    )
    api_key: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="PMS API Key（生产环境加密存储）"
    )
    webhook_secret: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Webhook 验签密钥"
    )

    # ── 映射配置 ──
    field_map_overrides: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="入驻时 AI 辅助生成 + 人工确认后的个性化映射规则，合并到默认映射之上"
    )
    room_type_mapping: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="房型名称 → 平台 PropertyType 的映射 { 'Ensuite Single': 'studio', ... }"
    )

    # ── 运行状态 ──
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_status: Mapped[PMSSyncStatus] = mapped_column(
        Enum(PMSSyncStatus, name="pms_sync_status"),
        default=PMSSyncStatus.idle, nullable=False,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_properties_synced: Mapped[int] = mapped_column(Integer, default=0)

    # ── 关系 ──
    institute: Mapped["Institute"] = relationship(back_populates="pms_connections")

    def __repr__(self) -> str:
        return f"<PMSConnection {self.label} ({self.pms_type.value})>"

"""租客档案模型 — 长久化保留，关联平台用户，可复用"""
import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class HousingStatus(str, enum.Enum):
    active = "active"               # 在住
    notice_given = "notice_given"   # 已通知退租
    moved_out = "moved_out"         # 已搬出


class Tenant(Base):
    """租客档案 — 一个 user 可创建多个 tenant 记录"""
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="租客标签")

    # ── 个人信息（14 字段，名复用 booking_flow_drafts.personal_info JSONB 的 key）──
    chinese_name:      Mapped[str | None] = mapped_column(String(100), nullable=True)
    given_name_pinyin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    surname_pinyin:    Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date:        Mapped[date | None] = mapped_column(Date, nullable=True)
    gender:            Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone:             Mapped[str | None] = mapped_column(String(32), nullable=True)
    email:             Mapped[str | None] = mapped_column(String(255), nullable=True)
    nationality:       Mapped[str | None] = mapped_column(String(100), nullable=True)
    school_name:       Mapped[str | None] = mapped_column(String(200), nullable=True)
    enrollment_grade:  Mapped[str | None] = mapped_column(String(100), nullable=True)
    major_english:     Mapped[str | None] = mapped_column(String(200), nullable=True)
    region:            Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_detail:    Mapped[str | None] = mapped_column(String(500), nullable=True)
    postal_code:       Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── 紧急联系人（12 字段，加 emergency_ 前缀区分）──
    emergency_chinese_name:      Mapped[str | None] = mapped_column(String(100), nullable=True)
    emergency_given_name_pinyin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    emergency_surname_pinyin:    Mapped[str | None] = mapped_column(String(100), nullable=True)
    emergency_relation:          Mapped[str | None] = mapped_column(String(50), nullable=True)
    emergency_birth_date:        Mapped[date | None] = mapped_column(Date, nullable=True)
    emergency_phone:             Mapped[str | None] = mapped_column(String(32), nullable=True)
    emergency_email:             Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_gender:            Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_region:            Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_address_detail:    Mapped[str | None] = mapped_column(String(500), nullable=True)
    emergency_postal_code:       Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_consultant_id:     Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── 居住状态 ──
    current_unit_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit_types.id", ondelete="SET NULL"), nullable=True, index=True
    )
    room_number: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="房间号")

    housing_status: Mapped[HousingStatus | None] = mapped_column(
        String(20), nullable=True, default="active"
    )
    move_in_date:  Mapped[date | None] = mapped_column(Date, nullable=True)
    move_out_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── 时间戳 ──
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    # ── 关系 ──
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    unit_type: Mapped["UnitType | None"] = relationship(foreign_keys=[current_unit_type_id])

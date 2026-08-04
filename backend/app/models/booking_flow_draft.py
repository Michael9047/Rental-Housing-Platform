"""预订流程草稿模型 — 存流程中间态，个人信息走 Tenant 表"""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class BookingFlowDraft(TimestampMixin, Base):
    __tablename__ = "booking_flow_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    unit_type_id: Mapped[int] = mapped_column(
        ForeignKey("unit_types.id", ondelete="SET NULL"), index=True, nullable=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), index=True, nullable=True
    )
    current_step: Mapped[str] = mapped_column(String(32), default="move_in_date")
    move_in_date: Mapped[str | None] = mapped_column(String(32))
    lease_months: Mapped[int | None] = mapped_column(Integer)

    @property
    def property_id(self) -> int | None:
        return self.unit_type_id

    @property
    def personal_info(self) -> dict | None:
        if not self.tenant:
            return None
        keys = [
            "chinese_name", "given_name_pinyin", "surname_pinyin", "birth_date",
            "gender", "phone", "email", "nationality", "school_name",
            "enrollment_grade", "major_english", "region", "address_detail",
            "postal_code",
        ]
        data = {key: getattr(self.tenant, key) for key in keys}
        if data.get("birth_date"):
            data["birth_date"] = data["birth_date"].isoformat()
        return data

    @property
    def emergency_contact(self) -> dict | None:
        if not self.tenant:
            return None
        mapping = {
            "chinese_name": "emergency_chinese_name",
            "given_name_pinyin": "emergency_given_name_pinyin",
            "surname_pinyin": "emergency_surname_pinyin",
            "relation": "emergency_relation",
            "birth_date": "emergency_birth_date",
            "phone": "emergency_phone",
            "email": "emergency_email",
            "gender": "emergency_gender",
            "region": "emergency_region",
            "address_detail": "emergency_address_detail",
            "postal_code": "emergency_postal_code",
            "consultant_id": "emergency_consultant_id",
        }
        data = {key: getattr(self.tenant, attr) for key, attr in mapping.items()}
        if data.get("birth_date"):
            data["birth_date"] = data["birth_date"].isoformat()
        return data

    # ── 关系 ──
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    unit_type: Mapped["UnitType | None"] = relationship(foreign_keys=[unit_type_id])
    tenant: Mapped["Tenant | None"] = relationship(foreign_keys=[tenant_id])

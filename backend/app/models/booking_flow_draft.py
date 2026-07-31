"""预订流程草稿模型 — 存流程中间态，个人信息走 Tenant 表"""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class BookingFlowDraft(TimestampMixin, Base):
    __tablename__ = "booking_flow_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
<<<<<<< HEAD
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
=======
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    unit_type_id: Mapped[int] = mapped_column(
        ForeignKey("unit_types.id", ondelete="SET NULL"), index=True, nullable=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), index=True, nullable=True
    )
>>>>>>> merge/pr33-pr35
    current_step: Mapped[str] = mapped_column(String(32), default="move_in_date")
    move_in_date: Mapped[str | None] = mapped_column(String(32))
    lease_months: Mapped[int | None] = mapped_column(Integer)

    # ── 关系 ──
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    unit_type: Mapped["UnitType | None"] = relationship(foreign_keys=[unit_type_id])
    tenant: Mapped["Tenant | None"] = relationship(foreign_keys=[tenant_id])

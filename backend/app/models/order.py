"""订单记录模型"""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class Order(TimestampMixin, Base):
    """订单记录"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("properties.id", ondelete="SET NULL"), index=True, nullable=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), index=True, nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    room: Mapped["Room | None"] = relationship()
    tenant: Mapped["Tenant | None"] = relationship()

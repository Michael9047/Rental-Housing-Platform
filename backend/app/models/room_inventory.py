"""公寓实际房号库存及订单房号确认审计模型。"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base


class RoomInventory(Base):
    __tablename__ = "room_inventory"
    __table_args__ = (UniqueConstraint("institute_id", "room_number", name="uq_room_inventory_institute_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institute_id: Mapped[int] = mapped_column(ForeignKey("institutes.id", ondelete="CASCADE"), index=True)
    unit_type_id: Mapped[int | None] = mapped_column(ForeignKey("unit_types.id", ondelete="SET NULL"), index=True)
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    floor: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BookingRoomAssignment(Base):
    __tablename__ = "booking_room_assignments"
    __table_args__ = (UniqueConstraint("booking_id", name="uq_booking_room_assignment_booking"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"), index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("room_inventory.id", ondelete="RESTRICT"), index=True)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

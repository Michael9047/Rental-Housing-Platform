"""租房推荐 Agent —— 购物车/候选清单模型"""
from sqlalchemy import ForeignKey, Text as SAText, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class AgentCart(TimestampMixin, Base):
    __tablename__ = "agent_carts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    items: Mapped[list["AgentCartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentCartItem(TimestampMixin, Base):
    __tablename__ = "agent_cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "unit_type_id", name="uq_agent_cart_items_cart_unit_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cart_id: Mapped[int] = mapped_column(
        ForeignKey("agent_carts.id", ondelete="CASCADE"), index=True
    )
    unit_type_id: Mapped[int] = mapped_column(
        ForeignKey("unit_types.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str | None] = mapped_column(SAText, nullable=True)

    cart: Mapped["AgentCart"] = relationship(back_populates="items")
    unit_type: Mapped["UnitType"] = relationship(lazy="selectin")

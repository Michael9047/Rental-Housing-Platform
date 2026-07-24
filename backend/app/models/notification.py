"""通知模型 — 站内消息、通知事件及投递记录"""
import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text as SAText, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


# ── 统一通知事件类型（与文档第3节对齐）──────────────────────────

class NotificationEventType(str, enum.Enum):
    """业务事件类型 — 订单/合同/支付状态变化驱动"""
    # 合同
    CONTRACT_SIGNED = "contract_signed"
    CONTRACT_EXPIRING = "contract_expiring"
    # 支付
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_PROCESSING = "payment_processing"
    PAYMENT_EXPIRING_IN_3_HOURS = "payment_expiring_in_3_hours"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_REVIEW = "payment_review"
    # 订单
    BOOKING_CONFIRMED = "booking_confirmed"
    ORDER_AUTO_CANCELLED = "order_auto_cancelled"
    # 退款
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


# ── 向后兼容的旧类型枚举（保留，供现有代码平滑过渡）──────────

class NotificationType(str, enum.Enum):
    """旧版通知类型 — 保留向后兼容，逐步迁移到 NotificationEventType"""
    booking_created = "booking_created"
    booking_approved = "booking_approved"
    booking_rejected = "booking_rejected"
    booking_cancelled = "booking_cancelled"
    booking_completed = "booking_completed"
    payment_received = "payment_received"
    payment_created = "payment_created"
    payment_failed = "payment_failed"
    payment_expired = "payment_expired"
    contract_generated = "contract_generated"
    contract_signed = "contract_signed"
    auth_registration = "auth_registration"
    auth_password_reset = "auth_password_reset"
    repair_created = "repair_created"
    repair_assigned = "repair_assigned"
    repair_completed = "repair_completed"
    repair_status_change = "repair_status_change"
    system = "system"


# ── 渠道枚举 ─────────────────────────────────────────────────

class NotificationChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    in_app = "in_app"


# ── 投递状态枚举 ─────────────────────────────────────────────

class DeliveryStatus(str, enum.Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    skipped = "skipped"


# ── 通知实体类型枚举 ──────────────────────────────────────────

class NotificationEntityType(str, enum.Enum):
    order = "order"
    payment = "payment"
    contract = "contract"
    booking = "booking"
    property = "property"
    repair = "repair"
    system = "system"


# ======================================================================
# 站内通知模型
# ======================================================================

class Notification(TimestampMixin, Base):
    """站内通知 — 消息中心 + 铃铛的数据源。

    每条通知对应一个用户可见的消息卡片，包含：
    - 事件类型（决定UI展示样式）
    - 结构化关联（order_id / property_id 等，支持订单跳转）
    - 已读状态（驱动铃铛角标）
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # 事件类型 — 使用新枚举，兼容旧值
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(SAText)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)

    # ── 结构化关联（用于订单跳转、实体导航）──────────────────
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    agreement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    property_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), index=True, nullable=True
    )

    user: Mapped["User"] = relationship()


# ======================================================================
# 通知投递记录（Outbox / 可靠性追踪）
# ======================================================================

class NotificationDelivery(TimestampMixin, Base):
    """统一通知投递记录 — 每条记录代表一次向某个渠道的发送尝试。

    对应文档第10节「通知记录模型」：
    - 幂等键唯一约束防止重复发送
    - 状态机追踪发送生命周期
    - 保存服务商消息ID用于对账
    """
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    notification_id: Mapped[int | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL"), index=True, nullable=True
    )
    order_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)

    # 渠道与事件
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 收件人（脱敏）
    recipient_masked: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 幂等键 — 数据库唯一索引保证不重复
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # 服务商消息ID（用于查询发送状态、投递回执）
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 状态机
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 时间戳
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 错误信息（仅保留错误码，不泄漏内部堆栈）
    last_error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

"""通知相关 Pydantic schemas"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── 站内通知 ──────────────────────────────────────────────────

class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    title: str
    content: str | None = None
    is_read: bool

    # 结构化关联
    entity_type: str | None = None
    entity_id: str | None = None
    order_id: int | None = None
    agreement_id: str | None = None
    property_id: int | None = None

    created_at: datetime
    updated_at: datetime


class NotificationListParams(BaseModel):
    """通知列表查询参数"""
    filter: str | None = Field(default=None, description="all | unread")
    entity_type: str | None = Field(default=None, description="按实体类型筛选")


class UnreadCount(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    detail: str = "All notifications marked as read"
    affected: int = 0


# ── 投递记录 ──────────────────────────────────────────────────

class DeliveryRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    notification_id: int | None = None
    order_id: int | None = None
    channel: str
    event_type: str
    template_id: str | None = None
    recipient_masked: str | None = None
    idempotency_key: str
    provider_message_id: str | None = None
    status: str
    attempt_count: int
    queued_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    last_error_code: str | None = None
    created_at: datetime


# ── 测试场景触发 ──────────────────────────────────────────────

class TestScenarioRequest(BaseModel):
    """测试场景触发请求"""
    scenario: str = Field(
        description="场景标识: contract_signed, payment_pending, payment_failed, "
                    "payment_processing, payment_expiring_3h, payment_succeeded, "
                    "booking_confirmed, order_auto_cancelled, payment_review, "
                    "refund_pending, refunded, contract_expiring"
    )
    user_id: int | None = Field(default=None, description="目标用户ID，默认使用当前用户")
    order_id: int | None = Field(default=None, description="关联订单ID")
    property_id: int | None = Field(default=None, description="关联房源ID")


class TestScenarioResponse(BaseModel):
    scenario: str
    notification_id: int | None = None
    delivery_ids: list[int] = []
    channels_sent: list[str] = []
    detail: str

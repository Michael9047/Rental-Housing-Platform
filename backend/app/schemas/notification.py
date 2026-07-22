from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: NotificationType
    title: str
    content: str | None
    body: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    order_id: str | None = None
    agreement_id: str | None = None
    property_id: int | None = None
    can_pay: bool = False
    payment_status: str | None = None
    order_status: str | None = None
    is_read: bool
    created_at: datetime
    updated_at: datetime


class UnreadCount(BaseModel):
    count: int

class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    page: int = 1
    page_size: int = 50

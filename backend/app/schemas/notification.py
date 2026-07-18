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
    is_read: bool
    created_at: datetime
    updated_at: datetime


class UnreadCount(BaseModel):
    count: int

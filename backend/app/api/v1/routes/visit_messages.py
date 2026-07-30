"""预约看房消息 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.models.institute import Institute
from app.models.visit_message import VisitMessage

router = APIRouter(prefix="/apartment", tags=["visit-messages"])


class SubmitVisitApply(BaseModel):
    apartment_id: int = Field(..., alias="apartmentId")
    guest_phone: str = Field(..., alias="guestPhone", min_length=1, max_length=32)
    guest_message: str = Field(default="", alias="guestMessage", max_length=500)


class VisitMessageRead(BaseModel):
    id: int
    apartment_id: int
    guest_phone: str
    guest_message: str | None = None
    is_read: bool
    created_at: str
    model_config = {"from_attributes": True}


# ── 租客提交预约看房 ──
@router.post("/submitVisitApply", status_code=201)
async def submit_visit_apply(data: SubmitVisitApply, session: AsyncSession = Depends(get_db_session)):
    apt = await session.get(Institute, data.apartment_id)
    if not apt:
        raise HTTPException(400, "公寓不存在")
    phone = data.guest_phone.strip()
    if not phone or not phone.isdigit():
        raise HTTPException(400, "请输入正确的手机号码")
    msg = VisitMessage(
        apartment_id=data.apartment_id,
        guest_phone=phone,
        guest_message=data.guest_message.strip() or None,
    )
    session.add(msg)
    await session.flush()

    # 给公寓创建者发一条站内通知
    from app.models.notification import Notification, NotificationType
    notif = Notification(
        user_id=apt.created_by,
        type=NotificationType.system,
        title="新的预约看房申请",
        content=f"手机号 {phone} 提交了看房申请" + (f"：{data.guest_message.strip()}" if data.guest_message.strip() else ""),
        body=f"手机号 {phone} 提交了看房申请" + (f"：{data.guest_message.strip()}" if data.guest_message.strip() else ""),
        entity_type="visit_message",
        entity_id=str(msg.id),
        property_id=data.apartment_id,
    )
    session.add(notif)

    await session.commit()
    return {"ok": True, "message": "预约信息已发送给公寓管理员"}


# ── 管理员获取预约消息列表 ──
@router.get("/admin/getVisitMessageList", response_model=list[VisitMessageRead])
async def get_visit_message_list(
    apartment_id: int = Query(..., alias="apartmentId"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    # 权限校验：只能看自己管理的公寓
    apt = await session.get(Institute, apartment_id)
    if not apt or (apt.created_by != current_user.id and current_user.role.value != "admin"):
        raise HTTPException(403, "无权查看该公寓的预约消息")
    result = await session.scalars(
        select(VisitMessage)
        .where(VisitMessage.apartment_id == apartment_id)
        .order_by(desc(VisitMessage.created_at))
    )
    items = result.all()
    return [
        VisitMessageRead(
            id=m.id, apartment_id=m.apartment_id,
            guest_phone=m.guest_phone, guest_message=m.guest_message,
            is_read=m.is_read,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in items
    ]


# ── 管理员标记已读 ──
@router.put("/admin/markVisitMsgRead")
async def mark_visit_msg_read(
    message_id: int = Query(..., alias="messageId"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    msg = await session.get(VisitMessage, message_id)
    if not msg:
        raise HTTPException(404, "消息不存在")
    # 权限校验
    apt = await session.get(Institute, msg.apartment_id)
    if not apt or (apt.created_by != current_user.id and current_user.role.value != "admin"):
        raise HTTPException(403, "无权操作")
    msg.is_read = True
    await session.commit()
    return {"ok": True}

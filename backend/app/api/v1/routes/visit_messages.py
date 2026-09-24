"""预约看房消息 API。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.institute import Institute
from app.models.user import User
from app.models.visit_message import VisitMessage

router = APIRouter(prefix="/apartment", tags=["visit-messages"])


class SubmitVisitApply(BaseModel):
    apartment_id: int = Field(..., alias="apartmentId")
    guest_phone: str = Field(..., alias="guestPhone", min_length=1, max_length=32)
    guest_message: str = Field(default="", alias="guestMessage", max_length=500)


class VisitMessageRead(BaseModel):
    id: int
    apartment_id: int
    apartment_name: str | None = None
    guest_phone: str
    guest_message: str | None = None
    is_read: bool
    created_at: str
    model_config = {"from_attributes": True}


def _can_manage_apartment(apt: Institute | None, user: User) -> bool:
    """判断当前用户是否有权查看或处理该公寓的看房申请。"""
    if not apt:
        return False
    if user.role.value == "admin":
        return True
    return apt.created_by == user.id or apt.bm_id == user.id


@router.post("/submitVisitApply", status_code=201)
async def submit_visit_apply(data: SubmitVisitApply, session: AsyncSession = Depends(get_db_session)):
    """租客提交预约看房申请。"""
    apt = await session.get(Institute, data.apartment_id)
    if not apt:
        raise HTTPException(400, "公寓不存在")

    phone = data.guest_phone.strip()
    if not phone or not phone.isdigit():
        raise HTTPException(400, "请输入正确的手机号码")

    message = data.guest_message.strip()
    msg = VisitMessage(
        apartment_id=data.apartment_id,
        guest_phone=phone,
        guest_message=message or None,
    )
    session.add(msg)
    await session.flush()

    # 新申请优先通知负责 BM；没有 BM 时回退给公寓创建者。
    from app.models.notification import Notification, NotificationType

    content = f"手机号 {phone} 提交了看房申请" + (f"：{message}" if message else "")
    session.add(Notification(
        user_id=apt.bm_id or apt.created_by,
        type=NotificationType.system,
        title="新的预约看房申请",
        content=content,
        body=content,
        entity_type="visit_message",
        entity_id=str(msg.id),
        unit_type_id=None,
    ))

    await session.commit()
    return {"ok": True, "message": "预约信息已发送给公寓管理员"}


@router.get("/admin/getVisitMessageList", response_model=list[VisitMessageRead])
async def get_visit_message_list(
    apartment_id: int | None = Query(default=None, alias="apartmentId"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """管理员查看看房申请；不传 apartmentId 时返回自己负责的全部公寓。"""
    stmt = select(VisitMessage, Institute.name).join(Institute, VisitMessage.apartment_id == Institute.id)
    if apartment_id is not None:
        apt = await session.get(Institute, apartment_id)
        if not _can_manage_apartment(apt, current_user):
            raise HTTPException(403, "无权查看该公寓的预约消息")
        stmt = stmt.where(VisitMessage.apartment_id == apartment_id)
    elif current_user.role.value != "admin":
        stmt = stmt.where(or_(Institute.created_by == current_user.id, Institute.bm_id == current_user.id))

    rows = (await session.execute(stmt.order_by(desc(VisitMessage.created_at)))).all()
    return [
        VisitMessageRead(
            id=message.id,
            apartment_id=message.apartment_id,
            apartment_name=apartment_name,
            guest_phone=message.guest_phone,
            guest_message=message.guest_message,
            is_read=message.is_read,
            created_at=message.created_at.isoformat() if message.created_at else "",
        )
        for message, apartment_name in rows
    ]


@router.put("/admin/markVisitMsgRead")
async def mark_visit_msg_read(
    message_id: int = Query(..., alias="messageId"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """将看房申请标记为已读。"""
    msg = await session.get(VisitMessage, message_id)
    if not msg:
        raise HTTPException(404, "消息不存在")

    apt = await session.get(Institute, msg.apartment_id)
    if not _can_manage_apartment(apt, current_user):
        raise HTTPException(403, "无权操作")

    msg.is_read = True
    await session.commit()
    return {"ok": True}

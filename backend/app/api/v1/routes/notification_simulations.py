"""仅开发环境管理员可用的订单通知模拟接口。"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import get_settings
from app.models.booking import Booking
from app.models.institute import Institute
from app.models.user import User, UserRole
from app.services.institute_access import can_manage_institute, managed_institute_filter
from app.services.notification_simulation_service import ALL_EVENTS, NotificationSimulationService

router = APIRouter()


class NotificationSimulationRequest(BaseModel):
    booking_id: int
    event_type: str
    outcome: Literal["success", "retry_success", "failed"] = "success"


@router.get("/events")
async def list_events(current_user: User = Depends(get_current_user)) -> dict:
    if current_user.role not in {UserRole.admin, UserRole.landlord}:
        raise HTTPException(403, "仅授权管理员可查看通知模拟事件")
    return {"items": sorted(ALL_EVENTS)}


@router.get("/orders")
async def list_simulation_orders(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """只返回当前管理员权限范围内的近期订单，供演示页安全选择。"""
    if current_user.role not in {UserRole.admin, UserRole.landlord}:
        raise HTTPException(403, "仅授权管理员可查看通知模拟订单")
    statement = select(Booking).order_by(Booking.updated_at.desc()).limit(100)
    scope = managed_institute_filter(current_user)
    if scope is not None:
        statement = statement.join(Institute, Booking.institute_id == Institute.id).where(scope)
    rows = list(await session.scalars(statement))
    return {"items": [{"id": booking.id, "status": booking.status.value, "institute_id": booking.institute_id} for booking in rows]}


@router.post("/dispatch")
async def dispatch_notification_simulation(
    payload: NotificationSimulationRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    if get_settings().environment.lower() == "production":
        raise HTTPException(404, "生产环境不提供通知模拟功能")
    if current_user.role not in {UserRole.admin, UserRole.landlord}:
        raise HTTPException(403, "仅授权管理员可以触发通知模拟")
    booking = await session.scalar(select(Booking).where(Booking.id == payload.booking_id))
    if not booking:
        raise HTTPException(404, "订单不存在")
    if current_user.role != UserRole.admin and not booking.institute_id:
        raise HTTPException(403, "当前订单未关联可管理的公寓")
    if current_user.role != UserRole.admin and not await can_manage_institute(session, current_user, booking.institute_id):
        raise HTTPException(403, "无权操作该公寓的订单")
    try:
        result = await NotificationSimulationService(session).dispatch(booking, payload.event_type, payload.outcome)
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(422, str(exc)) from exc
    return {"booking_id": booking.id, "event_type": payload.event_type, "outcome": payload.outcome, "results": [item.__dict__ for item in result]}

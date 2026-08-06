"""BM 房号确认工作台接口。"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session, require_landlord
from app.models.booking import Booking, BookingStatus
from app.models.contract_template import ContractTemplate
from app.models.institute import Institute
from app.models.room_inventory import BookingRoomAssignment, RoomInventory
from app.models.user import User, UserRole
from app.models.unit_type import UnitType
from app.services.institute_access import managed_institute_filter
from app.services.lease_pricing_service import LeasePricingService

router = APIRouter()

class RoomConfirmPayload(BaseModel):
    room_number: str = Field(min_length=1, max_length=50)
    contract_start: date | None = None
    contract_end: date | None = None

class RoomCreatePayload(BaseModel):
    institute_id: int
    unit_type_id: int | None = None
    room_number: str = Field(min_length=1, max_length=50)
    floor: str | None = Field(default=None, max_length=20)

class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; room_number: str; floor: str | None; status: str; unit_type_id: int | None

@router.get("/pending")
async def list_pending_confirmations(session: AsyncSession = Depends(get_db_session), current_user: User = Depends(require_landlord)) -> dict:
    stmt = select(Booking).join(Institute, Booking.institute_id == Institute.id).options(
        selectinload(Booking.tenant), selectinload(Booking.unit_type).selectinload(UnitType.institute)
    ).where(Booking.status == BookingStatus.paid)
    scope = managed_institute_filter(current_user)
    if scope is not None: stmt = stmt.where(scope)
    bookings = list((await session.scalars(stmt.order_by(Booking.created_at.asc()))).unique())
    items=[]
    for booking in bookings:
        rooms = list((await session.scalars(select(RoomInventory).where(
            RoomInventory.institute_id == booking.institute_id, RoomInventory.status == "available", RoomInventory.is_active.is_(True),
            (RoomInventory.unit_type_id == booking.unit_type_id) | (RoomInventory.unit_type_id.is_(None)),
        ).order_by(RoomInventory.room_number))).all())
        tenant=booking.tenant; unit=booking.unit_type; institute=unit.institute if unit else None
        items.append({"booking_id":booking.id,"institute_id":booking.institute_id,"institute_name":getattr(institute,"name_cn",None) or getattr(institute,"name",None),"unit_type_id":booking.unit_type_id,"unit_type_name":getattr(unit,"name",None),"tenant_name":getattr(tenant,"chinese_name",None) or getattr(tenant,"given_name_pinyin",None) or "未填写","tenant_phone":getattr(tenant,"phone",None),"move_in_date":booking.scheduled_date,"lease_months":booking.lease_months,"total_rent":booking.total_rent,"created_at":booking.created_at,"available_rooms":[RoomRead.model_validate(room).model_dump() for room in rooms]})
    return {"items":items,"total":len(items)}

@router.post("/rooms", response_model=RoomRead, status_code=201)
async def create_room(payload: RoomCreatePayload, session: AsyncSession = Depends(get_db_session), current_user: User = Depends(require_landlord)) -> RoomInventory:
    institute=await session.get(Institute,payload.institute_id)
    if not institute or (current_user.role != UserRole.admin and institute.bm_id != current_user.id): raise HTTPException(403,"无权管理该公寓房号库存")
    if payload.unit_type_id:
        unit=await session.get(UnitType,payload.unit_type_id)
        if not unit or unit.institute_id != institute.id: raise HTTPException(422,"户型不属于该公寓")
    room=RoomInventory(**payload.model_dump(),room_number=payload.room_number.strip())
    session.add(room)
    try: await session.commit()
    except Exception: await session.rollback(); raise HTTPException(409,"该公寓房号已存在")
    await session.refresh(room); return room

@router.post("/{booking_id}/confirm")
async def confirm_room(booking_id:int,payload:RoomConfirmPayload,session:AsyncSession=Depends(get_db_session),current_user:User=Depends(require_landlord))->dict:
    booking=await session.scalar(select(Booking).where(Booking.id==booking_id).with_for_update())
    if not booking: raise HTTPException(404,"订单不存在")
    institute=await session.get(Institute,booking.institute_id)
    if not institute or (current_user.role != UserRole.admin and institute.bm_id != current_user.id): raise HTTPException(403,"无权确认该订单房号")
    if booking.status != BookingStatus.paid: raise HTTPException(409,"只有支付成功的订单可以确认房号")
    if await session.scalar(select(BookingRoomAssignment.id).where(BookingRoomAssignment.booking_id==booking.id)): raise HTTPException(409,"订单已确认房号")
    room_number = payload.room_number.strip()
    room=await session.scalar(select(RoomInventory).where(RoomInventory.institute_id==booking.institute_id, RoomInventory.room_number==room_number).with_for_update())
    created_on_confirmation = False
    if not room:
        # 平台不预加载公寓全量房号。只有 BM 根据公寓方的真实确认输入房号时，
        # 才在同一事务中登记该房号并立即锁定，避免把未确认的房号当成库存。
        room = RoomInventory(
            institute_id=booking.institute_id,
            unit_type_id=booking.unit_type_id,
            room_number=room_number,
            status="available",
            is_active=True,
        )
        session.add(room)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(409, "该房号正在由其他确认请求登记，请刷新后重试") from exc
        created_on_confirmation = True
    if room.status!="available" or not room.is_active: raise HTTPException(409,"房号不可用或已被占用")
    if room.unit_type_id and room.unit_type_id != booking.unit_type_id: raise HTTPException(422,"房号与订单户型不匹配")
    contract_start = payload.contract_start or (date.fromisoformat(booking.scheduled_date) if booking.scheduled_date else None)
    contract_end = payload.contract_end or (
        LeasePricingService.add_calendar_months(contract_start, booking.lease_months)
        if contract_start and booking.lease_months else None
    )
    if not contract_start or not contract_end:
        raise HTTPException(422, "订单缺少入住日期或租期，无法生成合同结束日期")
    if contract_end <= contract_start:
        raise HTTPException(422, "合同结束日期必须晚于入住日期")

    room.status="reserved"; booking.room_number=room.room_number; booking.contract_start=contract_start; booking.contract_end=contract_end; booking.status=BookingStatus.contract_ready
    from app.services.contract_pdf_render_service import ContractPdfRenderService, ContractRenderError
    from app.services.contract_service import ContractService
    session.add(BookingRoomAssignment(booking_id=booking.id,room_id=room.id,confirmed_by=current_user.id))
    await session.commit()
    from app.services.notification_service import NotificationService
    from app.models.notification import NotificationType
    try:
        contract = await ContractService(session).generate_contract(booking)
        await ContractPdfRenderService(session).render_current_contract(contract)
        await NotificationService(session).create_notification(
            user_id=booking.user_id, type=NotificationType.contract_generated,
            title="您的租赁合同已生成", content=f"房号 {room.room_number} 已确认，请查看并签署合同。", channels=["email"],
        )
    except Exception as exc:
        raise HTTPException(500, "房号已确认，但合同生成或通知发送失败，请联系管理员") from exc
    return {"booking_id":booking.id,"room_number":room.room_number,"contract_id":contract.id,"status":booking.status.value,"contract_mode":"system_default_experiment","room_registered_on_confirmation":created_on_confirmation}

@router.post("/{booking_id}/cancel")
async def cancel_booking_by_bm(booking_id:int, session:AsyncSession=Depends(get_db_session), current_user:User=Depends(require_landlord))->dict:
    booking=await session.scalar(select(Booking).where(Booking.id==booking_id).with_for_update())
    if not booking: raise HTTPException(404,"订单不存在")
    institute=await session.get(Institute,booking.institute_id)
    if not institute or (current_user.role != UserRole.admin and institute.bm_id != current_user.id): raise HTTPException(403,"无权取消该订单")
    if booking.status not in {BookingStatus.payment_pending,BookingStatus.pending,BookingStatus.paid}: raise HTTPException(409,"订单当前不能取消")
    booking.status=BookingStatus.cancelled
    from app.services.notification_service import NotificationService
    from app.models.notification import NotificationType
    await NotificationService(session).create_notification(user_id=booking.user_id,type=NotificationType.booking_cancelled,title="您的订单已取消",content="公寓管理员已取消该订单；如有疑问请联系平台客服。",channels=["email"])
    await session.commit()
    return {"booking_id":booking.id,"status":booking.status.value}

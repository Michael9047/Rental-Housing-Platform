"""预约服务 — 基于 UnitType + 新 Booking 模型。"""
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingStatus
from app.models.institute import Institute
from app.models.notification import NotificationType
from app.models.unit_type import UnitType
from app.schemas.booking import BookingCreate
from app.services.notification_service import NotificationService


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_booking(
        self,
        user_id: int,
        unit_type_id: int,
        bm_id: int = 0,
        *,
        tenant_id: int | None = None,
        booking_in: BookingCreate | None = None,
    ) -> Booking:
        """创建预约 — 使用 unit_type_id 替代旧的 property_id。"""
        # 检查重复预约
        existing = await self.session.execute(
            select(Booking).where(
                and_(
                    Booking.user_id == user_id,
                    Booking.unit_type_id == unit_type_id,
                    Booking.status == BookingStatus.pending,
                )
            )
        )
        if existing.scalars().first():
            raise ValueError("You already have a pending booking for this unit type")

        # 获取 UnitType 获取定价信息
        unit_type = await self.session.get(UnitType, unit_type_id)
        deposit_amount = unit_type.deposit_amount if unit_type else 1000
        base_rent = int(unit_type.base_rent) if unit_type and unit_type.base_rent else 0
        service_fee = int(base_rent * 0.10) if base_rent else 0
        institute_id = unit_type.institute_id if unit_type else None
        institute = await self.session.get(Institute, institute_id) if institute_id else None
        resolved_bm_id = bm_id or (institute.bm_id if institute else None) or 1

        booking = Booking(
            user_id=user_id,
            tenant_id=tenant_id or user_id,
            property_id=unit_type_id,
            landlord_id=resolved_bm_id,
            unit_type_id=unit_type_id,
            institute_id=institute_id,
            bm_id=resolved_bm_id,
            message=booking_in.message if booking_in else None,
            scheduled_date=booking_in.scheduled_date if booking_in else None,
            deposit_amount=booking_in.deposit_amount if booking_in and booking_in.deposit_amount else deposit_amount,
            service_fee=booking_in.service_fee if booking_in and booking_in.service_fee else service_fee,
            deposit_status="unpaid",
            lease_months=booking_in.lease_months if booking_in else None,
            total_rent=booking_in.total_rent if booking_in else None,
            application_data=booking_in.application_data if booking_in else None,
        )
        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)

        # 通知 BM
        if bm_id:
            notification_service = NotificationService(self.session)
            await notification_service.create_notification(
                user_id=bm_id,
                type=NotificationType.booking_created,
                title="新的预约请求",
                content=f"有租客预约了户型 #{unit_type_id}（{unit_type.name if unit_type else ''}）",
                channels=[],
            )

        return booking

    async def update_status(self, booking_id: int, status: BookingStatus) -> Booking | None:
        booking = await self.session.get(Booking, booking_id)
        if not booking:
            return None

        booking.status = status
        await self.session.commit()
        await self.session.refresh(booking)

        notification_service = NotificationService(self.session)
        nt_map = {
            BookingStatus.approved: (
                NotificationType.booking_approved,
                "预约已通过",
                "您的预约已被批准",
                booking.user_id,
                [],
            ),
            BookingStatus.rejected: (
                NotificationType.booking_rejected,
                "预约已拒绝",
                "您的预约已被拒绝",
                booking.user_id,
                [],
            ),
            BookingStatus.cancelled: (
                NotificationType.booking_cancelled,
                "预约已取消",
                "一个预约已被取消",
                booking.bm_id,
                [],
            ),
            BookingStatus.completed: (
                NotificationType.booking_completed,
                "预约已完成",
                "预约流程已完成",
                booking.user_id,
                [],
            ),
        }
        if status in nt_map:
            nt_type, title, content, notify_user, channels = nt_map[status]
            if notify_user:
                await notification_service.create_notification(
                    user_id=notify_user,
                    type=nt_type,
                    title=title,
                    content=content,
                    channels=channels,
                )

            if status == BookingStatus.completed and booking.bm_id:
                await notification_service.create_notification(
                    user_id=booking.bm_id,
                    type=NotificationType.booking_completed,
                    title="预约已完成",
                    content=f"预约 #{booking.id} 已完成",
                    channels=[],
                )

        return booking

    async def list_by_tenant(self, tenant_id: int) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(Booking.user_id == tenant_id)
            .order_by(Booking.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def list_by_landlord(self, bm_id: int) -> list[Booking]:
        """按 BM 列出预约（兼容旧 landlord_id 参数名）。"""
        stmt = (
            select(Booking)
            .where(Booking.bm_id == bm_id)
            .order_by(Booking.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def get(self, booking_id: int) -> Booking | None:
        return await self.session.get(Booking, booking_id)

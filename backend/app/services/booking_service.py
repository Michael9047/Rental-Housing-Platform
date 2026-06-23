from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.notification import NotificationType
from app.schemas.booking import BookingCreate
from app.services.notification_service import NotificationService


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_booking(
        self,
        tenant_id: int,
        property_id: int,
        landlord_id: int,
        booking_in: BookingCreate,
    ) -> Booking:

        existing = await self.session.execute(
            select(Booking).where(
                and_(
                    Booking.tenant_id == tenant_id,
                    Booking.property_id == property_id,
                    Booking.status == BookingStatus.pending,
                )
            )
        )
        if existing.scalars().first():
            raise ValueError("You already have a pending booking for this property")

        booking = Booking(
            tenant_id=tenant_id,
            property_id=property_id,
            landlord_id=landlord_id,
            message=booking_in.message,
            scheduled_date=booking_in.scheduled_date,
        )
        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)

        notification_service = NotificationService(self.session)
        await notification_service.create_notification(
            user_id=landlord_id,
            type=NotificationType.booking_created,
            title="New booking request",
            content=f"A tenant has requested to view your property #{property_id}",
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
            BookingStatus.approved: (NotificationType.booking_approved, "Booking approved", "Your booking has been approved"),
            BookingStatus.rejected: (NotificationType.booking_rejected, "Booking rejected", "Your booking has been rejected"),
            BookingStatus.cancelled: (NotificationType.booking_cancelled, "Booking cancelled", "A booking has been cancelled"),
        }
        if status in nt_map:
            nt_type, title, content = nt_map[status]

            if status == BookingStatus.cancelled:
                notify_user = booking.landlord_id
            else:
                notify_user = booking.tenant_id

            await notification_service.create_notification(
                user_id=notify_user,
                type=nt_type,
                title=title,
                content=content,
            )
        return booking

    async def list_by_tenant(self, tenant_id: int) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(Booking.tenant_id == tenant_id)
            .order_by(Booking.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def list_by_landlord(self, landlord_id: int) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(Booking.landlord_id == landlord_id)
            .order_by(Booking.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result)

    async def get(self, booking_id: int) -> Booking | None:
        return await self.session.get(Booking, booking_id)

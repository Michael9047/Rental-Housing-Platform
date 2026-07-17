from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.property import Property
from app.models.user import User


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stats(self) -> dict:
        total_users = await self.session.scalar(
            select(func.count(User.id))
        )
        total_properties = await self.session.scalar(
            select(func.count(Property.id))
        )
        total_bookings = await self.session.scalar(
            select(func.count(Booking.id))
        )
        pending_bookings = await self.session.scalar(
            select(func.count(Booking.id)).where(Booking.status == BookingStatus.pending)
        )

        district_result = await self.session.execute(
            select(Property.district, func.count(Property.id))
            .group_by(Property.district)
            .order_by(func.count(Property.id).desc())
            .limit(10)
        )
        properties_by_district = [
            {"district": row[0], "count": row[1]} for row in district_result.all()
        ]

        return {
            "total_users": total_users or 0,
            "total_properties": total_properties or 0,
            "total_bookings": total_bookings or 0,
            "pending_bookings": pending_bookings or 0,
            "properties_by_district": properties_by_district,
        }

"""户型可用性校验 — UnitType 中心的日期/租期冲突检查。"""
import logging
from datetime import date

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.unit_type import UnitType, UnitTypeStatus

logger = logging.getLogger(__name__)


class BookingAvailabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_unit_type(self, unit_type_id: int) -> UnitType | None:
        """按 ID 获取 UnitType，加载关联 Institute 信息。"""
        from sqlalchemy.orm import selectinload
        from app.models.institute import Institute
        stmt = (select(UnitType)
                .options(selectinload(UnitType.institute))
                .where(UnitType.id == unit_type_id))
        result = await self.session.scalars(stmt)
        return result.unique().first()

    async def get_property(self, unit_type_id: int):
        """兼容旧调用 — 等同于 get_unit_type。"""
        return await self.get_unit_type(unit_type_id)

    async def get_month_availability(self, ut: UnitType, year: int, month: int) -> dict:
        """获取 UnitType 指定月份的日期可用性。"""
        import calendar
        today = date.today()
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        existing = await self.session.scalars(
            select(Booking).where(
                and_(
                    Booking.unit_type_id == ut.id,
                    Booking.status.in_([
                        BookingStatus.pending, BookingStatus.approved,
                        BookingStatus.contract_ready, BookingStatus.contract_signed,
                        BookingStatus.payment_pending, BookingStatus.payment_processing,
                        BookingStatus.paid, BookingStatus.completed,
                    ]),
                )
            )
        )
        blocked = set()
        for b in existing:
            if b.scheduled_date:
                try:
                    bd = date.fromisoformat(b.scheduled_date)
                    if first_day <= bd <= last_day:
                        blocked.add(b.scheduled_date)
                except (ValueError, TypeError):
                    continue

        return {
            "property_id": ut.id,
            "timezone": "Asia/Shanghai",
            "local_today": today.isoformat(),
            "available_from": ut.available_from.isoformat() if ut.available_from else None,
            "blocked_dates": sorted(blocked),
        }

    async def validate(self, ut: UnitType, move_in_date_str: str) -> tuple[bool, str, dict]:
        """校验 UnitType 在指定日期的可预订性。"""
        try:
            move_in = date.fromisoformat(move_in_date_str) if isinstance(move_in_date_str, str) \
                else move_in_date_str
        except (ValueError, TypeError):
            return False, "入住日期格式无效", {}

        today = date.today()
        if move_in < today:
            return False, "入住日期不能早于今天", {}

        if ut.status != UnitTypeStatus.available:
            return False, "该户型当前不可预订", {}

        if ut.available_from and move_in < ut.available_from:
            return False, f"该户型最早 {ut.available_from} 可入住", {}

        existing = await self.session.scalars(
            select(Booking).where(
                and_(
                    Booking.unit_type_id == ut.id,
                    Booking.status.in_([
                        BookingStatus.pending, BookingStatus.approved,
                        BookingStatus.contract_ready, BookingStatus.contract_signed,
                        BookingStatus.payment_pending, BookingStatus.payment_processing,
                        BookingStatus.paid, BookingStatus.completed,
                    ]),
                )
            )
        )
        conflicts = [b for b in existing if b.scheduled_date == move_in_date_str]
        if conflicts:
            return False, "所选日期已被预订", {}

        return True, "", {"move_in_date": move_in_date_str}

    async def check_conflict(self, unit_type_id: int, move_in: date, lease_months: int) -> bool:
        """检查 UnitType 在给定租期内是否有冲突。"""
        from app.services.lease_pricing_service import LeasePricingService
        end_date = LeasePricingService.add_calendar_months(move_in, lease_months)
        candidates = await self.session.scalars(
            select(Booking).where(
                Booking.unit_type_id == unit_type_id,
                Booking.status.in_([
                    BookingStatus.contract_signed, BookingStatus.payment_pending,
                    BookingStatus.payment_processing, BookingStatus.paid,
                ]),
            )
        )
        for b in candidates:
            if not b.scheduled_date or not b.lease_months:
                continue
            try:
                b_start = date.fromisoformat(b.scheduled_date)
                b_end = LeasePricingService.add_calendar_months(b_start, b.lease_months)
                if move_in < b_end and b_start < end_date:
                    return True
            except (ValueError, TypeError):
                continue
        return False

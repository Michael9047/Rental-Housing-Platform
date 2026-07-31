<<<<<<< HEAD
"""房源可用性校验 — 确保所选日期/租期在允许范围且无冲突。"""
import logging
from datetime import date, datetime

from sqlalchemy import select, and_
=======
"""户型可用性检查服务（UnitType 中心）。"""
>>>>>>> merge/pr33-pr35
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.property import Room, RoomStatus

logger = logging.getLogger(__name__)


class BookingAvailabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

<<<<<<< HEAD
    async def get_property(self, property_id: int) -> Room | None:
        """按 ID 获取房源（兼容旧 property_id 命名）。"""
        return await self.session.get(Room, property_id)

    async def get_month_availability(self, room: Room, year: int, month: int) -> dict:
        """获取房源指定月份的日期可用性（供日历组件使用）。"""
        import calendar
        today = date.today()
        local_today = today.isoformat()
        available_from = room.available_from.isoformat() if room.available_from else None
        timezone_str = "Asia/Shanghai"

        # 获取该月所有冲突的预定日期
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        existing = await self.session.scalars(
            select(Booking).where(
                and_(
                    Booking.property_id == room.id,
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
            "property_id": room.id,
            "timezone": timezone_str,
            "local_today": local_today,
            "available_from": available_from,
            "blocked_dates": sorted(blocked),
        }

    async def validate(self, room: Room, move_in_date_str: str) -> tuple[bool, str, dict]:
        """校验房源在指定日期的可预订性。返回 (valid, reason, info)。"""
        try:
            move_in = date.fromisoformat(move_in_date_str) if isinstance(move_in_date_str, str) \
                else move_in_date_str
        except (ValueError, TypeError):
            return False, "入住日期格式无效", {}

        today = date.today()
        if move_in < today:
            return False, "入住日期不能早于今天", {}

        # 房源状态检查
        if room.status != RoomStatus.available.value:
            return False, "房源当前不可预订", {}

        # 可用日期范围检查
        if room.available_from and move_in < room.available_from:
            return False, f"房源最早 {room.available_from} 可入住", {}

        # 冲突预订检查
        existing = await self.session.scalars(
            select(Booking).where(
                and_(
                    Booking.property_id == room.id,
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

    async def check_conflict(self, room_id: int, move_in: date, lease_months: int) -> bool:
        """检查房源在给定租期内是否有冲突。"""
        from app.services.lease_pricing_service import LeasePricingService
        end_date = LeasePricingService.add_calendar_months(move_in, lease_months)
        candidates = await self.session.scalars(
            select(Booking).where(
                Booking.property_id == room_id,
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
=======
    async def get_unit_type(self, unit_type_id: int):
        """获取户型对象（原 get_property 改名，保持兼容）。"""
        return await PropertyService(self.session).get(unit_type_id)

    async def get_property(self, unit_type_id: int):
        """兼容旧调用 — 等同于 get_unit_type。"""
        return await self.get_unit_type(unit_type_id)

    async def validate(self, unit_type, move_in_date: str):
        """验证户型是否可预订。unit_type 为 UnitType 模型实例。返回 (valid, reason, detail)。"""
        if not unit_type:
            return False, "户型不存在", None
        if not move_in_date:
            return False, "请选择起租日期", None
        # 检查是否有空房
        if not getattr(unit_type, "has_vacancy", True):
            return False, "该户型已满", None
        if getattr(unit_type, "available_count", 1) <= 0:
            return False, "该户型已无剩余房间", None
        return True, "", None
>>>>>>> merge/pr33-pr35

"""统一计算订单占用的户型库存。"""
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.unit_type import UnitType


INVENTORY_OCCUPYING_STATUSES = (
    BookingStatus.contract_signed,
    BookingStatus.payment_pending,
    BookingStatus.payment_processing,
    BookingStatus.paid,
    BookingStatus.completed,
)


def occupied_booking_count_subquery():
    """返回与当前 UnitType 相关的有效订单数量子查询。"""
    return (
        select(func.count(Booking.id))
        .where(
            Booking.unit_type_id == UnitType.id,
            Booking.status.in_(INVENTORY_OCCUPYING_STATUSES),
        )
        .correlate(UnitType)
        .scalar_subquery()
    )


async def annotate_effective_inventory(
    session: AsyncSession,
    unit_types: Iterable[UnitType],
) -> None:
    """批量给已加载户型标注按有效订单计算的真实剩余量。"""
    items = list(unit_types)
    if not items:
        return
    rows = await session.execute(
        select(Booking.unit_type_id, func.count(Booking.id))
        .where(
            Booking.unit_type_id.in_([item.id for item in items]),
            Booking.status.in_(INVENTORY_OCCUPYING_STATUSES),
        )
        .group_by(Booking.unit_type_id)
    )
    occupied_by_unit_type = {unit_type_id: int(count) for unit_type_id, count in rows}
    for item in items:
        item._effective_available_count = max(
            0,
            int(item.total_count or 0) - occupied_by_unit_type.get(item.id, 0),
        )


async def sync_unit_type_inventory(
    session: AsyncSession,
    unit_type_id: int | None,
) -> None:
    """把持久化库存修正为总套数减去有效订单数。"""
    if unit_type_id is None:
        return
    unit_type = await session.get(UnitType, unit_type_id)
    if unit_type is None:
        return
    occupied_count = int(
        await session.scalar(
            select(func.count(Booking.id)).where(
                Booking.unit_type_id == unit_type_id,
                Booking.status.in_(INVENTORY_OCCUPYING_STATUSES),
            )
        )
        or 0
    )
    unit_type.available_count = max(0, int(unit_type.total_count or 0) - occupied_count)
    unit_type.has_vacancy = unit_type.available_count > 0

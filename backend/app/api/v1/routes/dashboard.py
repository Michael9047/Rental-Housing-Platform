"""角色数据台 API"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_landlord, require_bd_manager, require_maintenance
from app.models.booking import Booking, BookingStatus
from app.models.institute import Institute
from app.models.property import Property, PropertyStatus
from app.models.repair import RepairRequest, RepairStatus, RepairWorker, WorkerStatus
from app.models.user import User, UserRole

router = APIRouter()


@router.get("/landlord/dashboard")
async def landlord_dashboard(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """房东/Manager 数据台"""
    # 房源统计
    total_props = await session.scalar(
        select(func.count(Property.id)).where(Property.landlord_id == current_user.id)
    )
    available_props = await session.scalar(
        select(func.count(Property.id)).where(
            Property.landlord_id == current_user.id, Property.status == PropertyStatus.available
        )
    )
    rented_props = await session.scalar(
        select(func.count(Property.id)).where(
            Property.landlord_id == current_user.id, Property.status == PropertyStatus.rented
        )
    )
    maintenance_props = await session.scalar(
        select(func.count(Property.id)).where(
            Property.landlord_id == current_user.id, Property.status == PropertyStatus.maintenance
        )
    )

    # 预约统计
    pending_bookings = await session.scalar(
        select(func.count(Booking.id)).where(
            Booking.landlord_id == current_user.id, Booking.status == BookingStatus.pending
        )
    )

    # 报修统计
    pending_repairs = await session.scalar(
        select(func.count(RepairRequest.id)).where(
            RepairRequest.landlord_id == current_user.id,
            RepairRequest.status == RepairStatus.pending,
        )
    )
    in_progress_repairs = await session.scalar(
        select(func.count(RepairRequest.id)).where(
            RepairRequest.landlord_id == current_user.id,
            RepairRequest.status == RepairStatus.in_progress,
        )
    )

    # 维修师傅统计
    total_workers = await session.scalar(
        select(func.count(RepairWorker.id)).where(RepairWorker.manager_id == current_user.id)
    )
    available_workers = await session.scalar(
        select(func.count(RepairWorker.id)).where(
            RepairWorker.manager_id == current_user.id,
            RepairWorker.status == WorkerStatus.available,
        )
    )

    # 近30天报修趋势（简化版，返回总数即可）
    return {
        "properties": {
            "total": total_props or 0,
            "available": available_props or 0,
            "rented": rented_props or 0,
            "maintenance": maintenance_props or 0,
        },
        "bookings": {"pending": pending_bookings or 0},
        "repairs": {
            "pending": pending_repairs or 0,
            "in_progress": in_progress_repairs or 0,
        },
        "workers": {
            "total": total_workers or 0,
            "available": available_workers or 0,
        },
    }


@router.get("/bd/dashboard")
async def bd_dashboard(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_bd_manager),
):
    """BD经理数据台"""
    total_institutes = await session.scalar(select(func.count(Institute.id)))
    total_properties = await session.scalar(select(func.count(Property.id)))
    pending_bookings = await session.scalar(
        select(func.count(Booking.id)).where(Booking.status == BookingStatus.pending)
    )

    return {
        "institutes": total_institutes or 0,
        "total_properties": total_properties or 0,
        "pending_bookings": pending_bookings or 0,
    }


@router.get("/maintenance/dashboard")
async def maintenance_dashboard(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_maintenance),
):
    """维修师傅个人数据台"""
    my_orders = await session.scalar(
        select(func.count(RepairRequest.id)).where(
            RepairRequest.assigned_worker_id == current_user.id
        )
    )
    today_orders = await session.scalar(
        select(func.count(RepairRequest.id)).where(
            RepairRequest.assigned_worker_id == current_user.id,
            RepairRequest.status.in_([RepairStatus.assigned, RepairStatus.in_progress]),
        )
    )
    completed = await session.scalar(
        select(func.count(RepairRequest.id)).where(
            RepairRequest.assigned_worker_id == current_user.id,
            RepairRequest.status == RepairStatus.completed,
        )
    )

    # Worker profile
    worker_stmt = select(RepairWorker).where(RepairWorker.user_id == current_user.id)
    worker_result = await session.execute(worker_stmt)
    worker = worker_result.scalar_one_or_none()

    return {
        "total_orders": my_orders or 0,
        "today_orders": today_orders or 0,
        "completed": completed or 0,
        "worker_status": worker.status if worker else "available",
        "worker_rating": worker.rating if worker else 5.0,
    }

"""当前租客个人中心汇总接口。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_tenant
from app.models.user import User
from app.services.favorite_service import FavoriteService
from app.services.tenant_contract_service import TenantContractService
from app.services.tenant_order_service import TenantOrderService

router = APIRouter()


class DashboardSummary(BaseModel):
    viewing_appointments: int
    payable_orders: int
    signed_contracts: int
    favorites: int


@router.get("/dashboard-summary", response_model=DashboardSummary)
async def dashboard_summary(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> DashboardSummary:
    contracts = await TenantContractService(session).list_for_tenant(current_user.id)
    orders = await TenantOrderService(session).list_for_tenant(current_user.id)
    favorites = await FavoriteService(session).list_by_user(current_user.id)
    formal_booking_ids = {order.booking_id for order in orders}
    viewing_statuses = {"pending", "approved", "rejected", "cancelled", "completed"}
    from app.services.booking_service import BookingService
    bookings = await BookingService(session).list_by_tenant(current_user.id)
    appointments = [row for row in bookings if row.status.value in viewing_statuses and row.id not in formal_booking_ids]
    return DashboardSummary(
        viewing_appointments=len(appointments),
        payable_orders=sum(1 for row in orders if row.can_pay and row.payment_status in {"payment_pending", "payment_failed"}),
        signed_contracts=len(contracts),
        favorites=len(favorites),
    )

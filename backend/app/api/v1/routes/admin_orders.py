"""管理员最终订单只读查询：仅归档完成预订和最终取消订单。"""
from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session, require_landlord
from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract
from app.models.institute import Institute
from app.models.payment import Payment
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.institute_access import can_manage_institute

router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])

# 订单管理收录所有已进入支付流程及之后的订单（排除未支付的 pending/草稿状态）。
ACTIVE_ORDER_STATUSES = {
    BookingStatus.paid,
    BookingStatus.contract_ready,
    BookingStatus.contract_signed,
    BookingStatus.completed,
    BookingStatus.cancelled,
    BookingStatus.rejected,
    BookingStatus.payment_expired,
}

# 新流程在签署时写入 completed；contract_signed 用于兼容此前已经签好的历史订单。
FINAL_SUCCESS = {BookingStatus.contract_signed, BookingStatus.completed}
FINAL_CANCELLED = {
    BookingStatus.cancelled,
    BookingStatus.rejected,
    BookingStatus.payment_expired,
}

_CANCEL_REASON = {
    BookingStatus.cancelled: "已取消",
    BookingStatus.rejected: "审核未通过",
    BookingStatus.payment_expired: "超时未支付",
}


def _category(status: BookingStatus) -> str:
    if status in FINAL_SUCCESS:
        return "completed"
    if status in FINAL_CANCELLED:
        return "cancelled"
    return "active"


def _payment_amount_minor(payment: Payment | None, booking: Booking) -> int | None:
    """优先返回真实支付记录，未支付订单仅返回已有订单快照金额。"""
    if payment:
        if payment.settlement_amount_minor:
            return payment.settlement_amount_minor
        # 兼容历史支付记录的主币种金额字段，避免把真实旧订单强制显示为 2000。
        return payment.amount * 100
    if booking.deposit_amount is not None:
        return booking.deposit_amount * 100
    return None


def _tenant_display_name(tenant: Tenant | None, user: User | None) -> str:
    """订单展示优先使用租客档案姓名，账号名仅作为兜底。"""
    if tenant:
        if tenant.chinese_name:
            return tenant.chinese_name
        pinyin_parts = [
            part.strip()
            for part in (tenant.given_name_pinyin, tenant.surname_pinyin)
            if part and part.strip()
        ]
        if pinyin_parts:
            return " ".join(pinyin_parts)
        if tenant.preferred_name:
            return tenant.preferred_name
    return user.username if user else "-"


def _tenant_phone(tenant: Tenant | None, user: User | None) -> str | None:
    """订单展示优先使用租客档案手机号，账号手机号仅作为兜底。"""
    if tenant and tenant.phone:
        return tenant.phone
    return user.phone if user else None


def _row(booking: Booking, payment: Payment | None, contract: Contract | None = None) -> dict:
    unit_type = booking.unit_type
    tenant = booking.tenant
    user = booking.user
    is_cancelled = booking.status in FINAL_CANCELLED
    return {
        "id": booking.id,
        "tenant_name": _tenant_display_name(tenant, user),
        "phone": _tenant_phone(tenant, user),
        "institute_name": booking.institute.name if booking.institute else "-",
        "institute_id": getattr(booking, "institute_id", None),
        "property_address": getattr(booking.institute, "address", None),
        "property_city": getattr(booking.institute, "city", None),
        "property_country": getattr(booking.institute, "country", None),
        "unit_type_name": unit_type.name if unit_type else "-",
        "unit_type_id": getattr(booking, "unit_type_id", None),
        "property_type": getattr(unit_type, "property_type", None),
        "property_description": getattr(unit_type, "description", None),
        "property_image_url": (
            getattr(unit_type, "image_urls", None)[0]
            if getattr(unit_type, "image_urls", None)
            else None
        ),
        "room_number": booking.room_number,
        "move_in_date": booking.scheduled_date,
        "lease_months": booking.lease_months,
        "contract_start": booking.contract_start,
        "contract_end": booking.contract_end,
        "status": _category(booking.status),
        "status_source": booking.status.value,
        "status_reason": _CANCEL_REASON.get(booking.status) if is_cancelled else None,
        "created_at": booking.created_at,
        "finalized_at": booking.updated_at,
        "monthly_rent": unit_type.base_rent if unit_type else None,
        "total_rent": booking.total_rent,
        "property_deposit": unit_type.deposit_amount if unit_type else None,
        "property_currency": unit_type.currency if unit_type else None,
        "rent_period": unit_type.rent_period.value if unit_type else None,
        "booking_deposit_minor": _payment_amount_minor(payment, booking),
        "payment_currency": payment.settlement_currency if payment else "CNY",
        "payment_status": payment.status.value if payment else booking.deposit_status,
        "paid_at": payment.paid_at if payment else None,
        "payment_method": payment.payment_method if payment else None,
        "refund_status": payment.status.value if payment and payment.status.value in {"refund_pending", "refunded"} else None,
        "refund_at": payment.updated_at if payment and payment.status.value == "refunded" else None,
        "refund_reference": payment.provider_payment_id if payment and payment.status.value == "refunded" else None,
        "contract_status": contract.status if contract else None,
        "agreement_id": contract.id if contract else None,
        "agreement_number": contract.agreement_number if contract else None,
        "contract_template_name": contract.template_name if contract else None,
        "contract_template_version": contract.template_version if contract else None,
        "contract_generated_at": contract.generated_at if contract else None,
        "contract_signed_at": contract.signed_at if contract else None,
    }


def _base_statement(current_user: User):
    """构建受角色约束的订单查询，BM 通过 Institute 级别权限匹配。"""
    from app.services.institute_access import managed_institute_filter

    statement = select(Booking).where(
        Booking.status.in_(ACTIVE_ORDER_STATUSES)
    )
    if current_user.role != UserRole.admin:
        scope = managed_institute_filter(current_user)
        statement = statement.join(
            Institute, Booking.institute_id == Institute.id, isouter=True
        ).where(or_(Booking.bm_id == current_user.id, scope))
    return statement


def _latest_payments(payments: Iterable[Payment]) -> dict[int, Payment]:
    latest: dict[int, Payment] = {}
    for payment in payments:
        # 查询已按创建时间倒序排列，首次出现的即为最新支付记录。
        latest.setdefault(payment.booking_id, payment)
    return latest


@router.get("")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    status: str = Query("all", pattern="^(all|active|completed|cancelled)$"),
    institute_id: int | None = Query(None, ge=1),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """分页返回管理员有权查看的订单。"""
    statement = _base_statement(current_user)
    if status == "active":
        statement = statement.where(Booking.status.in_(ACTIVE_ORDER_STATUSES - FINAL_SUCCESS - FINAL_CANCELLED))
    elif status == "completed":
        statement = statement.where(Booking.status.in_(FINAL_SUCCESS))
    elif status == "cancelled":
        statement = statement.where(Booking.status.in_(FINAL_CANCELLED))

    if institute_id is not None:
        statement = statement.where(Booking.institute_id == institute_id)

    value = keyword.strip() if keyword else ""
    if value:
        like_value = f"%{value}%"
        statement = statement.where(
            or_(
                cast(Booking.id, String).ilike(like_value),
                Booking.user.has(
                    or_(
                        User.username.ilike(like_value),
                        User.phone.ilike(like_value),
                    )
                ),
                Booking.tenant.has(
                    or_(
                        Tenant.chinese_name.ilike(like_value),
                        Tenant.given_name_pinyin.ilike(like_value),
                        Tenant.surname_pinyin.ilike(like_value),
                        Tenant.preferred_name.ilike(like_value),
                        Tenant.phone.ilike(like_value),
                    )
                ),
                Booking.institute.has(Institute.name.ilike(like_value)),
            )
        )

    total = await session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    rows = list(
        (
            await session.scalars(
                statement.options(
                    selectinload(Booking.user),
                    selectinload(Booking.tenant),
                    selectinload(Booking.institute),
                    selectinload(Booking.unit_type),
                )
                .order_by(Booking.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).unique()
    )
    booking_ids = [row.id for row in rows]
    payments = []
    if booking_ids:
        payments = list(
            await session.scalars(
                select(Payment)
                .where(Payment.booking_id.in_(booking_ids))
                .order_by(Payment.created_at.desc())
            )
        )
    latest = _latest_payments(payments)
    contracts = []
    if booking_ids:
        contracts = list(
            await session.scalars(
                select(Contract)
                .where(Contract.booking_id.in_(booking_ids))
                .order_by(Contract.version.desc())
            )
        )
    latest_contracts = _latest_payments(contracts)
    return {
        "items": [_row(row, latest.get(row.id), latest_contracts.get(row.id)) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total or 0,
    }


@router.get("/{booking_id}")
async def get_order(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """返回单个最终订单；详情接口执行与列表相同的 BM 范围校验。"""
    statement = select(Booking).where(Booking.id == booking_id).options(
        selectinload(Booking.user),
        selectinload(Booking.tenant),
        selectinload(Booking.institute),
        selectinload(Booking.unit_type),
    )
    booking = await session.scalar(statement)
    if booking is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if booking.status not in ACTIVE_ORDER_STATUSES:
        raise HTTPException(status_code=404, detail="该订单尚未归档")
    if current_user.role != UserRole.admin:
        has_direct_access = booking.bm_id == current_user.id
        has_institute_access = bool(
            booking.institute_id
            and await can_manage_institute(session, current_user, booking.institute_id)
        )
        if not has_direct_access and not has_institute_access:
            raise HTTPException(status_code=403, detail="无权查看该订单")

    payment = await session.scalar(
        select(Payment)
        .where(Payment.booking_id == booking.id)
        .order_by(Payment.created_at.desc())
    )
    contract = await session.scalar(
        select(Contract)
        .where(Contract.booking_id == booking.id)
        .order_by(Contract.version.desc())
    )
    return _row(booking, payment, contract)

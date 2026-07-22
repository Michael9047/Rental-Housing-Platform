"""订单管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.models.order import Order
from app.schemas.tenant_order import OrderCreate, OrderUpdate, OrderRead, OrderListResponse

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead, status_code=201)
async def create_order(
    data: OrderCreate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    o = Order(**data.model_dump())
    session.add(o)
    await session.flush()
    await session.refresh(o)
    return _to_read(o)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str | None = Query(default=None),
):
    filters = []
    if status:
        filters.append(Order.status == status)

    base = select(func.count(Order.id))
    for f in filters:
        base = base.where(f)
    total = (await session.scalar(base)) or 0

    skip = (page - 1) * page_size
    stmt = (
        select(Order)
        .options(selectinload(Order.tenant))
        .order_by(Order.created_at.desc())
        .offset(skip).limit(page_size)
    )
    for f in filters:
        stmt = stmt.where(f)
    items = list((await session.scalars(stmt)).unique())

    return OrderListResponse(
        items=[_to_read(o) for o in items], total=total, page=page,
        page_size=page_size, total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, session: AsyncSession = Depends(get_db_session)):
    stmt = select(Order).options(selectinload(Order.tenant)).where(Order.id == order_id)
    o = (await session.scalars(stmt)).first()
    if not o:
        raise HTTPException(404, "订单不存在")
    return _to_read(o)


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order(
    order_id: int, data: OrderUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    o = await session.get(Order, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    await session.flush()
    await session.refresh(o)
    return _to_read(o)


def _to_read(o: Order) -> OrderRead:
    return OrderRead(
        id=o.id, room_id=o.room_id, tenant_id=o.tenant_id,
        tenant_name=o.tenant.name if o.tenant else None,
        start_date=o.start_date, end_date=o.end_date,
        total_amount=o.total_amount, status=o.status,
        created_at=o.created_at, updated_at=o.updated_at,
    )

"""房客管理路由 — 含户型库存联动"""
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db_session, require_landlord
from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.models.unit_type import UnitType
from app.models.booking import Booking, BookingStatus
from app.models.institute import Institute
from app.schemas.tenant_order import TenantCreate, TenantUpdate, TenantRead, TenantListResponse
from app.services.lease_pricing_service import LeasePricingService
from app.services.institute_access import managed_institute_filter

router = APIRouter(prefix="/tenants", tags=["tenants"])

TENANT_BOOKING_STATUSES = {
    BookingStatus.contract_signed,
    BookingStatus.completed,
}


def _managed_tenant_statement(current_user: User):
    """构建 BM 可见的已签约租客查询，权限规则与订单管理保持一致。"""
    statement = (
        select(Tenant, Booking)
        .join(Booking, Booking.tenant_id == Tenant.id)
        .join(Institute, Institute.id == Booking.institute_id)
        .where(Booking.status.in_(TENANT_BOOKING_STATUSES))
    )
    if current_user.role != UserRole.admin:
        statement = statement.where(
            or_(Booking.bm_id == current_user.id, managed_institute_filter(current_user))
        )
    return statement


def _managed_tenant_by_id_statement(current_user: User, tenant_id: int):
    """按管理范围查询单个租客，避免仅凭租客编号越权访问。"""
    return _managed_tenant_statement(current_user).where(Tenant.id == tenant_id)


async def _adjust_inventory(session: AsyncSession, unit_type_id: int | None, delta: int):
    """调整户型可租数量（delta 为正表示归还，为负表示占用）"""
    if unit_type_id is None:
        return
    ut = await session.get(UnitType, unit_type_id)
    if ut:
        ut.available_count = max(0, (ut.available_count or 0) + delta)
        ut.has_vacancy = ut.available_count > 0


@router.post("", response_model=TenantRead, status_code=201)
async def create_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    t = Tenant(user_id=current_user.id, **data.model_dump())
    session.add(t)
    await session.flush()

    # 库存联动：占用一套
    await _adjust_inventory(session, data.current_unit_type_id, -1)
    await session.commit()

    # 重新加载以获取 unit_type 关系（含 institute 链）
    result = await session.execute(
        select(Tenant).where(Tenant.id == t.id).options(
            selectinload(Tenant.unit_type).selectinload(UnitType.institute)
        )
    )
    t_loaded = result.scalars().first()
    if t_loaded: t = t_loaded
    return _to_read(t)


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
    current_user: User = Depends(require_landlord),
):
    filters = []
    if keyword:
        kw = f"%{keyword}%"
        filters.append(
            Tenant.surname_pinyin.ilike(kw) |
            Tenant.given_name_pinyin.ilike(kw) |
            Tenant.phone.ilike(kw) |
            Tenant.school_name.ilike(kw)
        )

    managed = _managed_tenant_statement(current_user)
    for f in filters:
        managed = managed.where(f)
    total = (await session.scalar(
        select(func.count(func.distinct(managed.subquery().c.id)))
    )) or 0

    skip = (page - 1) * page_size
    stmt = (
        managed.options(
            selectinload(Tenant.unit_type).selectinload(UnitType.institute),
            selectinload(Booking.unit_type).selectinload(UnitType.institute),
            selectinload(Booking.institute),
        )
        .order_by(Tenant.created_at.desc())
        .offset(skip).limit(page_size)
    )
    rows = list((await session.execute(stmt)).unique().all())
    items = []
    seen_tenant_ids: set[int] = set()
    for tenant, booking in rows:
        if tenant.id in seen_tenant_ids:
            continue
        seen_tenant_ids.add(tenant.id)
        items.append(_to_read(tenant, booking))

    return TenantListResponse(
        items=items,
        total=total, page=page, page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


# ── 当前用户的租客档案 CRUD（/my 必须在 /{tenant_id} 之前注册）──

@router.get("/my", response_model=list[TenantRead])
async def list_my_tenants(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的所有租客档案"""
    result = await session.execute(
        select(Tenant)
        .where(Tenant.user_id == current_user.id)
        .options(selectinload(Tenant.unit_type).selectinload(UnitType.institute))
        .order_by(Tenant.is_default.desc(), Tenant.created_at.desc())
    )
    tenants = result.scalars().all()
    return [_to_read(t) for t in tenants]


@router.post("/my", response_model=TenantRead, status_code=201)
async def create_my_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """当前用户新建租客档案"""
    t = Tenant(user_id=current_user.id, **data.model_dump())
    session.add(t)
    await session.flush()
    await session.commit()
    # 重新加载关系
    result = await session.execute(
        select(Tenant).where(Tenant.id == t.id).options(
            selectinload(Tenant.unit_type).selectinload(UnitType.institute)
        )
    )
    t = result.scalars().first() or t
    return _to_read(t)


@router.get("/my/{tenant_id}", response_model=TenantRead)
async def get_my_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的单个租客档案"""
    result = await session.execute(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.user_id == current_user.id)
        .options(selectinload(Tenant.unit_type).selectinload(UnitType.institute))
    )
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "租客档案不存在")
    return _to_read(t)


@router.patch("/my/{tenant_id}", response_model=TenantRead)
async def update_my_tenant(
    tenant_id: int,
    data: TenantUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """当前用户更新自己的租客档案"""
    result = await session.execute(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.user_id == current_user.id)
        .options(selectinload(Tenant.unit_type))
    )
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "租客档案不存在")

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(t, k, v)

    await session.commit()
    # 重新加载
    fresh = await session.execute(
        select(Tenant).where(Tenant.id == t.id).options(
            selectinload(Tenant.unit_type).selectinload(UnitType.institute)
        )
    )
    t = fresh.scalars().first() or t
    return _to_read(t)


@router.delete("/my/{tenant_id}", status_code=200)
async def delete_my_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """当前用户删除自己的租客档案"""
    t = await session.get(Tenant, tenant_id)
    if not t or t.user_id != current_user.id:
        raise HTTPException(404, "租客档案不存在")
    await session.delete(t)
    await session.commit()
    return {"ok": True, "detail": "租客档案已删除"}


@router.post("/my/{tenant_id}/default", response_model=TenantRead)
async def set_my_default_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """设为默认租客档案（先取消其他默认）"""
    t = await session.get(Tenant, tenant_id)
    if not t or t.user_id != current_user.id:
        raise HTTPException(404, "租客档案不存在")

    # 取消当前用户其他默认
    others = await session.execute(
        select(Tenant).where(Tenant.user_id == current_user.id, Tenant.is_default == True)
    )
    for other in others.scalars().all():
        other.is_default = False

    t.is_default = True
    await session.commit()

    # 重新加载
    result = await session.execute(
        select(Tenant).where(Tenant.id == t.id).options(
            selectinload(Tenant.unit_type).selectinload(UnitType.institute)
        )
    )
    t = result.scalars().first() or t
    return _to_read(t)


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    statement = _managed_tenant_by_id_statement(current_user, tenant_id).options(
        selectinload(Tenant.unit_type).selectinload(UnitType.institute),
        selectinload(Booking.unit_type).selectinload(UnitType.institute),
        selectinload(Booking.institute),
    )
    row = (await session.execute(statement)).unique().first()
    if not row:
        raise HTTPException(404, "房客不存在")
    tenant, booking = row
    return _to_read(tenant, booking)


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: int, data: TenantUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    statement = _managed_tenant_by_id_statement(current_user, tenant_id).options(
        selectinload(Tenant.unit_type)
    )
    row = (await session.execute(statement)).unique().first()
    if not row:
        raise HTTPException(404, "房客不存在")
    t, _booking = row

    old_unit_type_id = t.current_unit_type_id
    update_data = data.model_dump(exclude_unset=True)

    for k, v in update_data.items():
        setattr(t, k, v)

    # 库存联动：户型变更
    new_unit_type_id = update_data.get("current_unit_type_id", old_unit_type_id)
    if old_unit_type_id and old_unit_type_id != new_unit_type_id:
        await _adjust_inventory(session, old_unit_type_id, +1)  # 归还旧户型
    if new_unit_type_id and new_unit_type_id != old_unit_type_id:
        await _adjust_inventory(session, new_unit_type_id, -1)  # 占用新户型

    await session.commit()
    # 重新查询以加载 unit_type.institute 链
    fresh = await session.execute(
        select(Tenant).where(Tenant.id == t.id).options(
            selectinload(Tenant.unit_type).selectinload(UnitType.institute)
        )
    )
    t = fresh.scalars().first() or t
    return _to_read(t)


@router.delete("/{tenant_id}", status_code=200)
async def delete_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    row = (
        await session.execute(
            _managed_tenant_by_id_statement(current_user, tenant_id)
        )
    ).unique().first()
    if not row:
        raise HTTPException(404, "房客不存在")
    t, _booking = row

    # 库存联动：归还户型
    await _adjust_inventory(session, t.current_unit_type_id, +1)
    await session.delete(t)
    await session.commit()
    return {"ok": True, "detail": "房客已删除"}


def _to_read(t: Tenant, booking: Booking | None = None) -> TenantRead:
    """转换为响应模型，附加 unit_type_name + institute_name"""
    ut = booking.unit_type if booking and booking.unit_type else t.unit_type
    ut_name = ut.name if ut else None
    inst_name = None
    if booking and booking.institute:
        inst_name = booking.institute.name
    elif ut:
        try:
            inst_name = ut.institute.name if ut.institute else None
        except Exception:
            pass
    hs = getattr(t.housing_status, 'value', t.housing_status) if t.housing_status else None
    move_in_date = t.move_in_date
    move_out_date = t.move_out_date
    # 历史签约记录可能早于 contract_end 的写入逻辑。列表只读回填展示值，
    # 不修改任何既有租客或订单数据。
    if booking:
        move_in_date = move_in_date or booking.contract_start
        if move_in_date is None and booking.scheduled_date:
            move_in_date = date.fromisoformat(booking.scheduled_date)
        if move_out_date is None:
            move_out_date = booking.contract_end
        if move_out_date is None and move_in_date and booking.lease_months:
            move_out_date = LeasePricingService.add_calendar_months(move_in_date, booking.lease_months)

    profile = TenantRead.model_validate(t)
    return profile.model_copy(update={
        "current_unit_type_id": (booking.unit_type_id if booking else None) or t.current_unit_type_id,
        "unit_type_name": ut_name,
        "institute_name": inst_name,
        "room_number": (booking.room_number if booking else None) or t.room_number,
        "housing_status": hs,
        "move_in_date": move_in_date,
        "move_out_date": move_out_date,
        "created_at": t.created_at or datetime.utcnow(),
        "updated_at": t.updated_at or datetime.utcnow(),
    })

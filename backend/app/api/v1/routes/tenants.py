"""房客管理路由 — 含户型库存联动"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.models.tenant import Tenant
from app.models.unit_type import UnitType
from app.schemas.tenant_order import TenantCreate, TenantUpdate, TenantRead, TenantListResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


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

    base = select(func.count(Tenant.id))
    for f in filters:
        base = base.where(f)
    total = (await session.scalar(base)) or 0

    skip = (page - 1) * page_size
    stmt = (
        select(Tenant)
        .options(selectinload(Tenant.unit_type).selectinload(UnitType.institute))
        .order_by(Tenant.created_at.desc())
        .offset(skip).limit(page_size)
    )
    for f in filters:
        stmt = stmt.where(f)
    items = list((await session.scalars(stmt)).unique())

    return TenantListResponse(
        items=[_to_read(t) for t in items],
        total=total, page=page, page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(tenant_id: int, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id).options(
            selectinload(Tenant.unit_type).selectinload(UnitType.institute)
        )
    )
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "房客不存在")
    return _to_read(t)


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: int, data: TenantUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.unit_type))
    )
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "房客不存在")

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
    _current_user: User = Depends(require_landlord),
):
    t = await session.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(404, "房客不存在")

    # 库存联动：归还户型
    await _adjust_inventory(session, t.current_unit_type_id, +1)
    await session.delete(t)
    await session.commit()
    return {"ok": True, "detail": "房客已删除"}


def _to_read(t: Tenant) -> TenantRead:
    """转换为响应模型，附加 unit_type_name + institute_name"""
    ut = t.unit_type
    ut_name = ut.name if ut else None
    inst_name = None
    if ut:
        try:
            inst_name = ut.institute.name if ut.institute else None
        except Exception:
            pass
    hs = getattr(t.housing_status, 'value', t.housing_status) if t.housing_status else None
    return TenantRead(
        id=t.id, surname_pinyin=t.surname_pinyin, given_name_pinyin=t.given_name_pinyin,
        chinese_name=t.chinese_name, phone=t.phone, email=t.email,
        school_name=t.school_name, current_unit_type_id=t.current_unit_type_id,
        unit_type_name=ut_name, institute_name=inst_name, room_number=t.room_number,
        housing_status=hs,
        move_in_date=t.move_in_date, move_out_date=t.move_out_date,
        label=t.label,
        created_at=t.created_at or datetime.utcnow(),
        updated_at=t.updated_at or datetime.utcnow(),
    )

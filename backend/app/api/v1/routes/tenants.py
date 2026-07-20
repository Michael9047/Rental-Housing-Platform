"""房客管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.tenant_order import TenantCreate, TenantUpdate, TenantRead, TenantListResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantRead, status_code=201)
async def create_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    t = Tenant(**data.model_dump())
    session.add(t)
    await session.flush()
    await session.refresh(t)
    return t


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
        filters.append(Tenant.name.ilike(kw) | Tenant.phone.ilike(kw))

    base = select(func.count(Tenant.id))
    for f in filters:
        base = base.where(f)
    total = (await session.scalar(base)) or 0

    skip = (page - 1) * page_size
    stmt = select(Tenant).order_by(Tenant.created_at.desc()).offset(skip).limit(page_size)
    for f in filters:
        stmt = stmt.where(f)
    items = list((await session.scalars(stmt)).unique())

    return TenantListResponse(items=items, total=total, page=page, page_size=page_size,
                              total_pages=max(1, (total + page_size - 1) // page_size))


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(tenant_id: int, session: AsyncSession = Depends(get_db_session)):
    t = await session.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(404, "房客不存在")
    return t


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: int, data: TenantUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    t = await session.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(404, "房客不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await session.flush()
    await session.refresh(t)
    return t

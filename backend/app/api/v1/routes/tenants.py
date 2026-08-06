"""租客档案管理路由 — 自服务 + 房东视角（v2）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.tenant_order import TenantCreate, TenantUpdate, TenantRead, TenantListResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


# ── 自服务：租客管理自己的档案 ──────────────────────────────


@router.get("/my", response_model=list[TenantRead])
async def list_my_tenants(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantRead]:
    """获取当前用户的所有租客档案（默认租客排前面）"""
    stmt = (
        select(Tenant)
        .where(Tenant.user_id == current_user.id)
        .order_by(Tenant.is_default.desc(), Tenant.created_at.desc())
    )
    result = await session.scalars(stmt)
    return list(result.unique())


@router.post("/my", response_model=TenantRead, status_code=201)
async def create_my_tenant(
    data: TenantCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TenantRead:
    """为当前用户创建租客档案"""
    t = Tenant(user_id=current_user.id, **data.model_dump(exclude_unset=True))
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


@router.get("/my/{tenant_id}", response_model=TenantRead)
async def get_my_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TenantRead:
    """获取自己的单个租客档案"""
    t = await session.get(Tenant, tenant_id)
    if not t or t.user_id != current_user.id:
        raise HTTPException(404, "租客档案不存在")
    return t


@router.patch("/my/{tenant_id}", response_model=TenantRead)
async def update_my_tenant(
    tenant_id: int,
    data: TenantUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TenantRead:
    """更新自己的租客档案"""
    t = await session.get(Tenant, tenant_id)
    if not t or t.user_id != current_user.id:
        raise HTTPException(404, "租客档案不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await session.commit()
    await session.refresh(t)
    return t


@router.delete("/my/{tenant_id}", status_code=204)
async def delete_my_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """删除自己的租客档案"""
    t = await session.get(Tenant, tenant_id)
    if not t or t.user_id != current_user.id:
        raise HTTPException(404, "租客档案不存在")
    await session.delete(t)
    await session.commit()


@router.post("/my/{tenant_id}/default", response_model=TenantRead)
async def set_default_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TenantRead:
    """设为默认租客（同时取消该用户其他默认）"""
    t = await session.get(Tenant, tenant_id)
    if not t or t.user_id != current_user.id:
        raise HTTPException(404, "租客档案不存在")

    # 取消该用户所有现有默认
    await session.execute(
        update(Tenant)
        .where(Tenant.user_id == current_user.id, Tenant.is_default == True)
        .values(is_default=False)
    )
    t.is_default = True
    await session.commit()
    await session.refresh(t)
    return t


# ── 房东/管理员视角（保留兼容旧版简化字段）──────────────────

from app.api.deps import require_landlord
from pydantic import BaseModel as PydanticBaseModel


class LegacyTenantCreate(PydanticBaseModel):
    """旧版创建租客 — 兼容 TenantManagement.vue 的 5 字段"""
    name: str
    phone: str | None = None
    email: str | None = None
    id_number: str | None = None
    emergency_contact: str | None = None


class LegacyTenantUpdate(PydanticBaseModel):
    """旧版更新租客"""
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    id_number: str | None = None
    emergency_contact: str | None = None


@router.post("", response_model=TenantRead, status_code=201)
async def create_tenant_landlord(
    data: LegacyTenantCreate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """房东创建租客（兼容旧版简化字段）"""
    t = Tenant(chinese_name=data.name, phone=data.phone, email=data.email)
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant_landlord(
    tenant_id: int,
    data: LegacyTenantUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """房东更新租客（兼容旧版简化字段）"""
    t = await session.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(404, "租客不存在")
    if data.name is not None:
        t.chinese_name = data.name
    if data.phone is not None:
        t.phone = data.phone
    if data.email is not None:
        t.email = data.email
    await session.commit()
    await session.refresh(t)
    return t


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None),
):
    """分页搜索租客（已修复 keyword 字段名）"""
    filters = []
    if keyword:
        kw = f"%{keyword}%"
        filters.append(Tenant.chinese_name.ilike(kw) | Tenant.phone.ilike(kw) | Tenant.label.ilike(kw))

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
        raise HTTPException(404, "租客不存在")
    return t

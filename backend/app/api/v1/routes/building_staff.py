"""公寓人员配置路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.models.building_staff import BuildingStaff
from app.schemas.building_staff import BuildingStaffCreate, BuildingStaffUpdate, BuildingStaffRead

router = APIRouter(tags=["building-staff"])


@router.get("/buildings/{institute_id}/staff", response_model=list[BuildingStaffRead])
async def list_staff(institute_id: int, session: AsyncSession = Depends(get_db_session)):
    """获取公寓全部人员（无状态过滤，返回所有记录）"""
    result = await session.scalars(
        select(BuildingStaff)
        .where(BuildingStaff.institute_id == institute_id)
        .order_by(BuildingStaff.id)
    )
    return list(result)


@router.post("/buildings/{institute_id}/staff", response_model=BuildingStaffRead, status_code=201)
async def create_staff(
    institute_id: int, data: BuildingStaffCreate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """新增人员 — 事务完整提交，返回完整数据"""
    staff = BuildingStaff(institute_id=institute_id, **data.model_dump())
    session.add(staff)
    await session.commit()  # 完整提交事务
    await session.refresh(staff)
    return staff


@router.patch("/buildings/{institute_id}/staff/{staff_id}", response_model=BuildingStaffRead)
async def update_staff(
    institute_id: int, staff_id: int, data: BuildingStaffUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    staff = await session.get(BuildingStaff, staff_id)
    if not staff:
        raise HTTPException(404, "人员不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(staff, k, v)
    await session.commit()
    await session.refresh(staff)
    return staff


@router.delete("/buildings/{institute_id}/staff/{staff_id}", status_code=204)
async def delete_staff(
    institute_id: int, staff_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    staff = await session.get(BuildingStaff, staff_id)
    if not staff:
        raise HTTPException(404, "人员不存在")
    await session.delete(staff)
    await session.commit()

"""公寓人员配置路由"""
import shutil
import uuid as _uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.core.config import get_settings
from app.models.user import User
from app.models.building_staff import BuildingStaff
from app.schemas.building_staff import BuildingStaffCreate, BuildingStaffUpdate, BuildingStaffRead

router = APIRouter(tags=["building-staff"])


def _move_qr_from_temp(filename: str | None) -> str | None:
    """将微信二维码从 temp 目录移到 uploads 根目录"""
    if not filename:
        return None
    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    # 检查是否已经是永久路径（不含 temp）
    src = upload_root / "temp"
    found = None
    for user_dir in src.glob("*"):
        candidate = user_dir / filename
        if candidate.exists():
            found = candidate
            break
    if found:
        new_name = f"qr_{_uuid.uuid4().hex[:12]}.png"
        try:
            shutil.move(str(found), str(upload_root / new_name))
            return new_name
        except Exception:
            pass
    return filename


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
    payload = data.model_dump()
    payload['wechat_qr'] = _move_qr_from_temp(payload.get('wechat_qr'))
    staff = BuildingStaff(institute_id=institute_id, **payload)
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
    update_data = data.model_dump(exclude_unset=True)
    if 'wechat_qr' in update_data:
        update_data['wechat_qr'] = _move_qr_from_temp(update_data['wechat_qr'])
    for k, v in update_data.items():
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

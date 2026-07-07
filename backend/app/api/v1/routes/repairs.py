"""维修工单 API"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_db_session,
    require_admin,
    require_landlord,
    require_maintenance,
    require_tenant,
)
from app.models.repair import RepairStatus
from app.models.user import User, UserRole
from app.schemas.repair import RepairCreate, RepairRead, RepairUpdate
from app.services.repair_service import RepairService

router = APIRouter()


async def _repair_to_read(repair) -> RepairRead:
    """将 RepairRequest ORM 对象转为 Read 响应（async-safe）"""
    # 用 awaitable_attrs 安全获取关联对象
    from sqlalchemy.ext.asyncio import AsyncAttrs
    tenant = await repair.awaitable_attrs.tenant if hasattr(repair, 'awaitable_attrs') and repair.tenant_id else None
    landlord = await repair.awaitable_attrs.landlord if hasattr(repair, 'awaitable_attrs') and repair.landlord_id else None
    worker = await repair.awaitable_attrs.assigned_worker if hasattr(repair, 'awaitable_attrs') and repair.assigned_worker_id else None
    prop = await repair.awaitable_attrs.property if hasattr(repair, 'awaitable_attrs') and repair.property_id else None

    return RepairRead(
        id=repair.id,
        property_id=repair.property_id,
        tenant_id=repair.tenant_id,
        landlord_id=repair.landlord_id,
        assigned_worker_id=repair.assigned_worker_id,
        issue_type=repair.issue_type,
        description=repair.description,
        images=repair.images,
        status=repair.status,
        scheduled_time=repair.scheduled_time,
        completed_at=repair.completed_at,
        work_record=repair.work_record,
        work_images=repair.work_images,
        created_at=repair.created_at.isoformat(),
        updated_at=repair.updated_at.isoformat(),
        tenant_name=tenant.username if tenant else None,
        landlord_name=landlord.username if landlord else None,
        worker_name=worker.username if worker else None,
        property_title=prop.title if prop else None,
    )


@router.post("/repairs", response_model=RepairRead)
async def create_repair(
    repair_in: RepairCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
):
    """租客提交报修申请"""
    svc = RepairService(session)
    try:
        repair = await svc.create_repair(current_user.id, repair_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await _repair_to_read(repair)


@router.get("/repairs")
async def list_repairs(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """按角色查看工单列表"""
    svc = RepairService(session)

    tenant_id = None
    landlord_id = None
    worker_id = None

    if current_user.role == UserRole.tenant:
        tenant_id = current_user.id
    elif current_user.role == UserRole.landlord:
        landlord_id = current_user.id
    elif current_user.role == UserRole.maintenance_worker:
        worker_id = current_user.id
    # admin 可以看到全部

    status_enum = RepairStatus(status_filter) if status_filter else None

    repairs = await svc.list_repairs(
        tenant_id=tenant_id,
        landlord_id=landlord_id,
        worker_id=worker_id,
        status=status_enum,
        skip=skip,
        limit=limit,
    )
    return [await _repair_to_read(r) for r in repairs]


@router.get("/repairs/{repair_id}", response_model=RepairRead)
async def get_repair(
    repair_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """查看工单详情"""
    svc = RepairService(session)
    repair = await svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")

    # 权限检查：租客/房东/维修师傅/管理员
    role = current_user.role
    if role == UserRole.tenant and repair.tenant_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if role == UserRole.landlord and repair.landlord_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if role == UserRole.maintenance_worker and repair.assigned_worker_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return await _repair_to_read(repair)


@router.patch("/repairs/{repair_id}/status", response_model=RepairRead)
async def update_repair_status(
    repair_id: int,
    new_status: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """房东审批/拒绝工单"""
    valid_statuses = {"approved", "rejected"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be: {valid_statuses}",
        )

    svc = RepairService(session)
    repair = await svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    if repair.landlord_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    status_enum = RepairStatus.approved if new_status == "approved" else RepairStatus.rejected
    repair = await svc.update_status(repair_id, status_enum, current_user.id)
    return await _repair_to_read(repair)


@router.patch("/repairs/{repair_id}/assign", response_model=RepairRead)
async def assign_worker(
    repair_id: int,
    worker_id: int = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """房东指派维修师傅"""
    svc = RepairService(session)
    repair = await svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    if repair.landlord_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        repair = await svc.assign_worker(repair_id, worker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await _repair_to_read(repair)


@router.patch("/repairs/{repair_id}/start", response_model=RepairRead)
async def start_repair(
    repair_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_maintenance),
):
    """维修师傅标记开始工作"""
    svc = RepairService(session)
    repair = await svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    if repair.assigned_worker_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    repair = await svc.start_work(repair_id)
    return await _repair_to_read(repair)


@router.patch("/repairs/{repair_id}/complete", response_model=RepairRead)
async def complete_repair(
    repair_id: int,
    work_record: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_maintenance),
):
    """维修师傅完成工单，填写维修记录"""
    svc = RepairService(session)
    repair = await svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    if repair.assigned_worker_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    repair = await svc.complete_work(repair_id, work_record)
    return await _repair_to_read(repair)


@router.patch("/repairs/{repair_id}/cancel", response_model=RepairRead)
async def cancel_repair(
    repair_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
):
    """租客取消报修"""
    svc = RepairService(session)
    repair = await svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    if repair.tenant_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    repair = await svc.cancel_repair(repair_id)
    return await _repair_to_read(repair)

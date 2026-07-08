"""维修师傅管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_admin, require_landlord, get_current_user
from app.models.repair import WorkerStatus
from app.models.user import User, UserRole
from app.schemas.repair import WorkerCreate, WorkerRead, WorkerStatusUpdate, WorkerUpdate
from app.services.worker_service import WorkerService

router = APIRouter()


def _worker_to_read(worker) -> WorkerRead:
    return WorkerRead(
        id=worker.id,
        user_id=worker.user_id,
        manager_id=worker.manager_id,
        status=worker.status,
        skills=worker.skills,
        phone=worker.phone,
        total_jobs=worker.total_jobs,
        rating=worker.rating,
        created_at=worker.created_at.isoformat(),
        username=getattr(worker.user, "username", None) if worker.user else None,
    )


@router.post("/repair-workers", response_model=WorkerRead)
async def create_worker(
    worker_in: WorkerCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """房东创建维修师傅账号"""
    svc = WorkerService(session)
    try:
        worker = await svc.create_worker(current_user.id, worker_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _worker_to_read(worker)


@router.get("/repair-workers")
async def list_workers(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """查看维修师傅列表（管理员看全部，房东看自己的）"""
    svc = WorkerService(session)
    if current_user.role == UserRole.admin:
        workers = await svc.list_all_workers()
    else:
        workers = await svc.list_workers(current_user.id)
    return [_worker_to_read(w) for w in workers]


@router.get("/repair-workers/{worker_id}", response_model=WorkerRead)
async def get_worker(
    worker_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """查看维修师傅详情"""
    svc = WorkerService(session)
    worker = await svc.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    # 权限：管理员可看全部，manager 只能看自己的，维修师傅本人
    if current_user.role != UserRole.admin:
        if current_user.role == UserRole.maintenance_worker and worker.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if current_user.role == UserRole.landlord and worker.manager_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _worker_to_read(worker)


@router.patch("/repair-workers/{worker_id}", response_model=WorkerRead)
async def update_worker(
    worker_id: int,
    update_in: WorkerUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """编辑维修师傅信息"""
    svc = WorkerService(session)
    worker = await svc.update_worker(worker_id, update_in)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return _worker_to_read(worker)


@router.patch("/repair-workers/{worker_id}/status", response_model=WorkerRead)
async def update_worker_status(
    worker_id: int,
    status_in: WorkerStatusUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """Manager 调整维修师傅工作状态（包括设为休假）"""
    svc = WorkerService(session)
    worker = await svc.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    if worker.manager_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    worker = await svc.update_worker_status(worker_id=worker_id, status_in=status_in)
    return _worker_to_read(worker)

"""维修师傅管理服务"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.repair import RepairWorker, WorkerStatus
from app.models.user import User, UserRole
from app.schemas.repair import WorkerCreate, WorkerUpdate, WorkerStatusUpdate


class WorkerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_worker(
        self, manager_id: int, worker_in: WorkerCreate
    ) -> RepairWorker:
        """房东创建维修师傅（同时创建 User 账号）"""
        # 检查用户名唯一性
        stmt = select(User).where(User.username == worker_in.username)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError(f"Username '{worker_in.username}' already exists")

        # 创建维修师傅的 User 账号
        from app.schemas.auth import RegisterRequest
        from app.services.auth_service import AuthService

        auth_svc = AuthService(self.session)
        new_user = await auth_svc.register_user(
            RegisterRequest(
                username=worker_in.username,
                password=worker_in.password,
                phone=worker_in.phone,
                role=UserRole.maintenance_worker,
            )
        )

        # 创建 RepairWorker 档案
        worker = RepairWorker(
            user_id=new_user.id,
            manager_id=manager_id,
            phone=worker_in.phone,
            skills=worker_in.skills or [],
            status=WorkerStatus.available,
        )
        self.session.add(worker)
        await self.session.commit()
        await self.session.refresh(worker)

        # 重新加载以获取关系数据
        return await self.get_worker(worker.id)

    async def list_workers(self, manager_id: int) -> list[RepairWorker]:
        """查看某 manager 管理的维修师傅列表"""
        stmt = (
            select(RepairWorker)
            .where(RepairWorker.manager_id == manager_id)
            .options(selectinload(RepairWorker.user))
            .order_by(RepairWorker.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_workers(
        self, skip: int = 0, limit: int = 100
    ) -> list[RepairWorker]:
        """管理员查看所有维修师傅"""
        stmt = (
            select(RepairWorker)
            .options(selectinload(RepairWorker.user))
            .order_by(RepairWorker.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_worker(self, worker_id: int) -> RepairWorker | None:
        stmt = (
            select(RepairWorker)
            .where(RepairWorker.id == worker_id)
            .options(selectinload(RepairWorker.user))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_worker_by_user_id(self, user_id: int) -> RepairWorker | None:
        stmt = (
            select(RepairWorker)
            .where(RepairWorker.user_id == user_id)
            .options(selectinload(RepairWorker.user))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_worker(
        self, worker_id: int, update_in: WorkerUpdate
    ) -> RepairWorker | None:
        worker = await self.get_worker(worker_id)
        if not worker:
            return None
        if update_in.phone is not None:
            worker.phone = update_in.phone
        if update_in.skills is not None:
            worker.skills = update_in.skills
        await self.session.commit()
        await self.session.refresh(worker)
        return worker

    async def update_worker_status(
        self,
        worker_id: int | None,
        user_id: int | None = None,
        status_in: WorkerStatusUpdate = None,
    ) -> RepairWorker | None:
        """调整维修师傅工作状态（包括设为休假）"""
        if worker_id:
            worker = await self.get_worker(worker_id)
        elif user_id:
            worker = await self.get_worker_by_user_id(user_id)
        else:
            return None
        if not worker:
            return None
        worker.status = status_in.status
        await self.session.commit()
        await self.session.refresh(worker)
        return worker

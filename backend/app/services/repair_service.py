"""维修工单服务"""
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.repair import RepairRequest, RepairStatus, RepairIssueType
from app.models.notification import NotificationType
from app.models.property import Property
from app.schemas.repair import RepairCreate, RepairUpdate
from app.services.notification_service import NotificationService


class RepairService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_repair(
        self, tenant_id: int, repair_in: RepairCreate
    ) -> RepairRequest:
        """租客创建报修申请"""
        # 查找房源和房东
        stmt = select(Property).where(Property.id == repair_in.property_id)
        result = await self.session.execute(stmt)
        property_obj = result.scalar_one_or_none()
        if not property_obj:
            raise ValueError("Property not found")

        repair = RepairRequest(
            property_id=repair_in.property_id,
            tenant_id=tenant_id,
            landlord_id=property_obj.landlord_id,
            issue_type=repair_in.issue_type,
            description=repair_in.description,
            images=repair_in.images,
            scheduled_time=repair_in.scheduled_time,
            status=RepairStatus.pending,
        )
        self.session.add(repair)
        await self.session.commit()

        # 通知房东
        notif_svc = NotificationService(self.session)
        await notif_svc.create_notification(
            user_id=property_obj.landlord_id,
            type=NotificationType.repair_created,
            title="新报修申请",
            content=f"租客对房源「{property_obj.title}」提交了报修：{repair_in.description[:50]}",
        )

        # Reload with relationships
        return await self.get_repair(repair.id)

    async def list_repairs(
        self,
        *,
        tenant_id: int | None = None,
        landlord_id: int | None = None,
        worker_id: int | None = None,
        status: RepairStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[RepairRequest]:
        """按角色过滤工单列表"""
        stmt = (
            select(RepairRequest)
            .options(
                selectinload(RepairRequest.tenant),
                selectinload(RepairRequest.landlord),
                selectinload(RepairRequest.assigned_worker),
                selectinload(RepairRequest.property),
            )
            .order_by(RepairRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        if tenant_id is not None:
            stmt = stmt.where(RepairRequest.tenant_id == tenant_id)
        if landlord_id is not None:
            stmt = stmt.where(RepairRequest.landlord_id == landlord_id)
        if worker_id is not None:
            stmt = stmt.where(RepairRequest.assigned_worker_id == worker_id)
        if status is not None:
            stmt = stmt.where(RepairRequest.status == status)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_repair(self, repair_id: int) -> RepairRequest | None:
        stmt = (
            select(RepairRequest)
            .where(RepairRequest.id == repair_id)
            .options(
                selectinload(RepairRequest.tenant),
                selectinload(RepairRequest.landlord),
                selectinload(RepairRequest.assigned_worker),
                selectinload(RepairRequest.property),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self, repair_id: int, new_status: RepairStatus, current_user_id: int
    ) -> RepairRequest | None:
        """更新工单状态"""
        repair = await self.get_repair(repair_id)
        if not repair:
            return None
        repair.status = new_status

        notif_svc = NotificationService(self.session)

        if new_status == RepairStatus.rejected:
            await notif_svc.create_notification(
                user_id=repair.tenant_id,
                type=NotificationType.repair_status_change,
                title="报修已被拒绝",
                content=f"您的报修已被房东拒绝",
            )
        elif new_status == RepairStatus.completed:
            await notif_svc.create_notification(
                user_id=repair.tenant_id,
                type=NotificationType.repair_completed,
                title="维修已完成",
                content=f"您的报修已维修完成",
            )

        await self.session.commit()
        return await self.get_repair(repair.id)

    async def assign_worker(
        self, repair_id: int, worker_id: int
    ) -> RepairRequest | None:
        """房东指派维修师傅"""
        repair = await self.get_repair(repair_id)
        if not repair:
            return None

        from app.models.repair import RepairWorker, WorkerStatus

        # 检查维修师傅状态
        worker_stmt = select(RepairWorker).where(RepairWorker.user_id == worker_id)
        worker_result = await self.session.execute(worker_stmt)
        worker = worker_result.scalar_one_or_none()
        if not worker:
            raise ValueError("Worker not found")
        if worker.status != WorkerStatus.available:
            raise ValueError("Worker is not available")

        repair.assigned_worker_id = worker_id
        repair.status = RepairStatus.assigned
        worker.status = WorkerStatus.working

        await self.session.commit()

        # 通知维修师傅
        notif_svc = NotificationService(self.session)
        await notif_svc.create_notification(
            user_id=worker_id,
            type=NotificationType.repair_assigned,
            title="新工单指派",
            content=f"您有一个新的维修工单：{repair.description[:50]}",
        )

        return await self.get_repair(repair.id)

    async def start_work(self, repair_id: int) -> RepairRequest | None:
        """维修师傅开始工作"""
        repair = await self.get_repair(repair_id)
        if not repair:
            return None
        repair.status = RepairStatus.in_progress
        await self.session.commit()
        return await self.get_repair(repair.id)

    async def complete_work(
        self,
        repair_id: int,
        work_record: str,
        work_images: list[str] | None = None,
    ) -> RepairRequest | None:
        """维修师傅完成工单"""
        from datetime import datetime, timezone

        repair = await self.get_repair(repair_id)
        if not repair:
            return None

        from app.models.repair import RepairWorker, WorkerStatus

        # 恢复维修师傅状态
        if repair.assigned_worker_id:
            worker_stmt = select(RepairWorker).where(
                RepairWorker.user_id == repair.assigned_worker_id
            )
            worker_result = await self.session.execute(worker_stmt)
            worker = worker_result.scalar_one_or_none()
            if worker:
                worker.status = WorkerStatus.available
                worker.total_jobs += 1

        repair.status = RepairStatus.completed
        repair.work_record = work_record
        repair.work_images = work_images
        repair.completed_at = datetime.now(timezone.utc).isoformat()

        await self.session.commit()

        # 通知租客
        notif_svc = NotificationService(self.session)
        await notif_svc.create_notification(
            user_id=repair.tenant_id,
            type=NotificationType.repair_completed,
            title="维修已完成",
            content=f"维修师傅已完成工单，维修记录：{work_record[:100]}",
        )

        return await self.get_repair(repair.id)

    async def cancel_repair(self, repair_id: int) -> RepairRequest | None:
        """租客取消报修"""
        repair = await self.get_repair(repair_id)
        if not repair:
            return None
        repair.status = RepairStatus.cancelled
        await self.session.commit()
        return await self.get_repair(repair.id)

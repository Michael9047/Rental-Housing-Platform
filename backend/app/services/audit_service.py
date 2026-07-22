from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_log(self, audit_log_id: int) -> AuditLog | None:
        stmt = select(AuditLog).where(AuditLog.id == audit_log_id)
        result = await self.session.scalars(stmt)
        return result.first()

    async def create_log(
        self,
        *,
        user_id: int | None,
        action: str,
        resource_type: str | None = None,
        resource_id: int | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def delete_log(self, audit_log_id: int) -> bool:
        log = await self.get_log(audit_log_id)
        if not log:
            return False
        await self.session.delete(log)
        await self.session.commit()
        return True

    async def batch_delete_logs(self, ids: list[int]) -> int:
        """批量删除审计日志，返回成功删除数"""
        deleted = 0
        for log_id in ids:
            if await self.delete_log(log_id):
                deleted += 1
        return deleted

    async def clear_logs(self, landlord_id: int) -> int:
        """清空当前房东所有房源相关的审计日志，返回删除数"""
        from app.models.property import Property
        prop_ids_stmt = select(Property.id).where(Property.landlord_id == landlord_id)
        result = await self.session.scalars(prop_ids_stmt)
        prop_ids = set(result.all())
        if not prop_ids:
            return 0
        logs_stmt = select(AuditLog).where(
            AuditLog.resource_type == "property",
            AuditLog.resource_id.in_(prop_ids),
        )
        logs_result = await self.session.scalars(logs_stmt)
        logs = list(logs_result)
        for log in logs:
            await self.session.delete(log)
        await self.session.commit()
        return len(logs)

    async def list_logs(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: int | None = None,
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id is not None:
            stmt = stmt.where(AuditLog.resource_id == resource_id)

        result = await self.session.scalars(stmt)
        return list(result)

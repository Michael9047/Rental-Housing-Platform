from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def list_logs(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        user_id: int | None = None,
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

        result = await self.session.scalars(stmt)
        return list(result)

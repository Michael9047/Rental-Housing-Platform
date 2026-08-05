from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_alert import SystemAlertProcessRecord
from app.models.user import User


async def record_alert_action(
    session: AsyncSession,
    current_user: User | None,
    *,
    alert_key: str,
    category: str,
    severity: str,
    title: str,
    source: str,
    source_id: str | int | None,
    action_type: str,
    note: str | None = None,
    status_before: str | None = None,
    status_after: str | None = None,
    system_alert_id: int | None = None,
    extra: dict | None = None,
) -> SystemAlertProcessRecord:
    record = SystemAlertProcessRecord(
        alert_key=alert_key,
        system_alert_id=system_alert_id,
        category=category,
        severity=severity,
        title=title,
        source=source,
        source_id=str(source_id) if source_id is not None else None,
        action_type=action_type,
        note=note,
        status_before=status_before,
        status_after=status_after,
        handled_by_id=current_user.id if current_user else None,
        extra=extra,
    )
    session.add(record)
    return record

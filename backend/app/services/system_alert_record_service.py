from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_alert import SystemAlertProcessRecord
from app.models.user import User

SYSTEM_ALERT_PROCESS_RECORD_RETENTION_DAYS = 180
RECORD_EXTRA_FIELDS = ("报错内容", "运行详情", "系统说明", "变更前", "变更后", "补充信息")


def _plain_record_value(value: object) -> str:
    if value is None or value == "":
        return "无"
    if hasattr(value, "value"):
        return str(value.value)
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (list, tuple, set)):
        return "、".join(_plain_record_value(item) for item in value) or "无"
    if isinstance(value, dict):
        return "；".join(f"{key}：{_plain_record_value(val)}" for key, val in value.items()) or "无"
    return str(value)


def _normalize_record_extra(
    extra: dict | None,
    *,
    status_before: str | None,
    status_after: str | None,
    note: str | None,
) -> dict:
    source = dict(extra or {})
    error_content = (
        source.get("报错内容")
        or source.get("错误原因")
        or source.get("异常原因")
        or source.get("补充信息")
        or source.get("detail")
        or note
        or "无"
    )
    runtime_details = source.get("运行详情") or source.get("变更前") or status_before or "无"
    system_note = source.get("系统说明") or source.get("变更后") or status_after or "无"

    normalized = {
        "报错内容": _plain_record_value(error_content),
        "运行详情": _plain_record_value(runtime_details),
        "系统说明": _plain_record_value(system_note),
    }
    for key, value in source.items():
        if key not in RECORD_EXTRA_FIELDS:
            normalized[key] = _plain_record_value(value)
    return normalized


async def purge_expired_alert_process_records(
    session: AsyncSession,
    *,
    retention_days: int = SYSTEM_ALERT_PROCESS_RECORD_RETENTION_DAYS,
) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await session.execute(
        delete(SystemAlertProcessRecord).where(SystemAlertProcessRecord.created_at < cutoff)
    )
    return int(result.rowcount or 0)


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
    await purge_expired_alert_process_records(session)
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
        extra=_normalize_record_extra(
            extra,
            status_before=status_before,
            status_after=status_after,
            note=note,
        ),
    )
    session.add(record)
    return record

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db_session, require_admin, require_landlord
from app.models.audit_log import AuditLog
from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract
from app.models.data_import import DataImport, ImportStatus
from app.models.embedding_job import EmbeddingJob, EmbeddingJobStatus
from app.models.institute import Institute, InstituteStatus
from app.models.notification import NotificationOutbox, NotificationOutboxStatus
from app.models.payment import Payment, PaymentStatus
from app.models.repair import RepairRequest, RepairStatus
from app.models.review import Review, ReviewStatus
from app.models.runtime_event import RuntimeEvent
from app.models.system_alert import (
    SystemAlert as PersistedSystemAlert,
    SystemAlertProcessRecord,
    SystemAlertSeverity,
    SystemAlertStatus,
)
from app.models.unit_type import UnitType, UnitTypeStatus
from app.models.user import User, UserRole
from app.schemas.system_alert import SystemAlertCreate
from app.schemas.unit_type import UnitTypeUpdate
from app.schemas.user import UserRead
from app.services.audit_service import AuditService
from app.services.embedding_job_service import EmbeddingJobService
from app.services.payment_provider import provider_availability
from app.services.property_service import PropertyService
from app.services.stats_service import StatsService
from app.services.system_alert_record_service import (
    SYSTEM_ALERT_PROCESS_RECORD_RETENTION_DAYS,
    purge_expired_alert_process_records,
    record_alert_action,
)
from app.services.unit_type_service import UnitTypeService
from app.services.user_service import UserService

router = APIRouter()


ALERT_CATEGORY_UNIT_TYPE = "户型信息"
ALERT_CATEGORY_ORDER = "订单信息"
ALERT_CATEGORY_BOOKING = "预约情况"
ALERT_CATEGORY_AI = "AI检索"
ALERT_CATEGORY_CONTRACT = "合同信息"
ALERT_CATEGORY_AFTER_SALES = "售后处理"
ALERT_CATEGORY_SYSTEM_API = "系统接口"
ALERT_CATEGORY_BACKOFFICE = "后台处理"

ALERT_CATEGORIES = [
    ALERT_CATEGORY_SYSTEM_API,
    ALERT_CATEGORY_AI,
    ALERT_CATEGORY_ORDER,
    ALERT_CATEGORY_CONTRACT,
    ALERT_CATEGORY_AFTER_SALES,
    ALERT_CATEGORY_BOOKING,
    ALERT_CATEGORY_UNIT_TYPE,
]

ALERT_DETECTION_TYPES = [
    {
        "key": "system_api",
        "category": ALERT_CATEGORY_SYSTEM_API,
        "name": "系统接口异常",
        "sources": ["notification_outbox", "payment_provider", "runtime_events"],
        "checks": ["通知发送失败", "支付接口不可用", "后端运行异常"],
    },
    {
        "key": "ai_search",
        "category": ALERT_CATEGORY_AI,
        "name": "AI检索异常",
        "sources": ["embedding_jobs"],
        "checks": ["索引任务失败", "索引任务超时"],
    },
    {
        "key": "order",
        "category": ALERT_CATEGORY_ORDER,
        "name": "订单信息异常",
        "sources": ["bookings"],
        "checks": ["支付窗口过期未自动关闭"],
    },
    {
        "key": "contract",
        "category": ALERT_CATEGORY_CONTRACT,
        "name": "合同异常",
        "sources": ["contracts"],
        "checks": ["合同 PDF 生成失败"],
    },
]


def _plain_value(value: object) -> str:
    if value is None or value == "":
        return "无"
    if hasattr(value, "value"):
        return str(value.value)
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (list, tuple, set)):
        return "、".join(_plain_value(item) for item in value) or "无"
    if isinstance(value, dict):
        return "；".join(f"{key}：{_plain_value(val)}" for key, val in value.items()) or "无"
    return str(value)


def _plain_pairs(values: dict[str, object] | None) -> str:
    if not values:
        return "无"
    return "；".join(f"{key}：{_plain_value(value)}" for key, value in values.items()) or "无"


def _first_plain(values: dict[str, object] | None, keys: tuple[str, ...]) -> str:
    if not values:
        return "无"
    for key in keys:
        value = values.get(key)
        if value is not None and value != "":
            return _plain_value(value)
    return "无"


def _alert_extra(
    before: dict[str, object] | None = None,
    after: dict[str, object] | None = None,
    note: str | None = None,
) -> dict:
    runtime_details = dict(before or {})
    system_details = {
        key: value
        for key, value in dict(after or {}).items()
        if key not in {"处理目标", "处理结果", "阅读状态"}
    }
    error_content = _first_plain(
        runtime_details,
        (
            "报错内容",
            "错误内容",
            "错误原因",
            "异常原因",
            "接口说明",
            "接口返回",
            "运行错误",
            "last_error",
            "error_message",
            "pdf_last_error",
        ),
    )
    if error_content == "无":
        error_content = _plain_value(note)
    return {
        "报错内容": error_content,
        "运行详情": _plain_pairs(runtime_details),
        "系统说明": _plain_pairs(system_details) if system_details else "无",
    }


def _ensure_alert_extra(alert: dict) -> dict:
    if alert.get("extra"):
        return alert
    alert["extra"] = _alert_extra(
        {"异常状态": alert.get("status"), "来源": alert.get("source"), "编号": alert.get("source_id")},
        {"报错位置": f"{alert.get('source') or '-'} / {alert.get('source_id') or '-'}"},
        alert.get("detail") or alert.get("summary"),
    )
    return alert


def _process_record_extra(row: SystemAlertProcessRecord) -> dict:
    extra = dict(row.extra or {})
    if {"报错内容", "运行详情", "系统说明"}.issubset(extra.keys()):
        return extra
    return _alert_extra(
        {"原状态": row.status_before, "来源": row.source, "编号": row.source_id},
        {"处理动作": row.action_type, "记录结果": row.status_after},
        _plain_pairs(extra) if extra else row.note,
    )


def _audit_details(log: AuditLog, unit_types: dict[int, UnitType]) -> dict:
    details = dict(log.details or {})
    if log.resource_type == "unit_type" and log.resource_id:
        unit_type = unit_types.get(log.resource_id)
        details.setdefault("table", "unit_types")
        details.setdefault("unit_type_id", log.resource_id)
        details.setdefault("institute_table", "institutes")
        if unit_type:
            if not details.get("unit_type_name"):
                details["unit_type_name"] = unit_type.name
            if not details.get("institute_id"):
                details["institute_id"] = unit_type.institute_id
            if not details.get("institute_name"):
                details["institute_name"] = unit_type.institute.name if unit_type.institute else None
    return details


class SystemAlertResolveRequest(BaseModel):
    note: str | None = None


class GeneratedSystemAlertResolveRequest(BaseModel):
    alert_key: str
    category: str
    severity: str
    title: str
    source: str
    source_id: str | int | None = None
    action_type: str | None = None
    status: str | None = None
    detail: str | None = None
    extra: dict | None = None
    note: str | None = None


class UnitTypeReviewRequest(BaseModel):
    result: str
    note: str | None = None


def _alert_action(
    action_type: str | None,
    action_label: str | None,
    action_resource_id: str | int | None,
) -> dict | None:
    if not action_type or not action_label:
        return None
    return {
        "type": action_type,
        "label": action_label,
        "resource_id": action_resource_id,
    }


def _persisted_alert_to_card(row: PersistedSystemAlert) -> dict:
    return {
        "id": f"system:{row.id}",
        "category": row.category,
        "severity": row.severity.value if hasattr(row.severity, "value") else str(row.severity),
        "title": row.title,
        "summary": row.summary,
        "detail": row.detail or "",
        "source": row.source,
        "source_id": row.source_id or row.id,
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "updated_at": row.updated_at.isoformat(),
        "extra": row.extra,
        "action": _alert_action(
            row.action_type or "resolve_system_alert",
            row.action_label or "标记处理",
            row.action_resource_id or row.id,
        ),
    }


def _is_generated_system_alert(
    category: str | None = None,
    *,
    alert_key: str | None = None,
    source: str | None = None,
    title: str | None = None,
) -> bool:
    key = alert_key or ""
    text = f"{title or ''} {source or ''} {key}"
    if category == ALERT_CATEGORY_AI:
        return True
    if source in {"embedding_job", "notification_outbox", "payment_provider", "runtime_event"}:
        return True
    if key.startswith(("ai_embedding_", "notification:", "payment_provider:", "runtime_event:")):
        return True
    if key.startswith("booking_payment_expired:"):
        return True
    if key.startswith("contract_pdf:"):
        return True
    if source == "payment" and ("支付失败" in text or "接口" in text):
        return True
    return False


def _generated_alert_action(alert: dict) -> dict:
    return {
        "type": "mark_alert_read",
        "label": "标为已读",
        "resource_id": alert["id"],
    }


@router.get("/overview")
async def get_admin_overview(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    role_rows = await session.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role = {
        (role.value if hasattr(role, "value") else str(role)): count
        for role, count in role_rows.all()
    }

    booking_rows = await session.execute(
        select(Booking.status, func.count(Booking.id)).group_by(Booking.status)
    )
    bookings_by_status = {
        (status.value if hasattr(status, "value") else str(status)): count
        for status, count in booking_rows.all()
    }

    payment_rows = await session.execute(
        select(Payment.status, func.count(Payment.id), func.coalesce(func.sum(Payment.settlement_amount_minor), 0))
        .group_by(Payment.status)
    )
    payments_by_status = [
        {
            "status": status.value if hasattr(status, "value") else str(status),
            "count": count,
            "settlement_amount_minor": int(amount or 0),
        }
        for status, count, amount in payment_rows.all()
    ]

    failed_notifications = await session.scalar(
        select(func.count(NotificationOutbox.id)).where(
            NotificationOutbox.status == NotificationOutboxStatus.failed
        )
    )
    recent_logs = await session.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(8)
    )

    return {
        "users": {
            "total": sum(users_by_role.values()),
            "by_role": {
                "admin": users_by_role.get(UserRole.admin.value, 0),
                "tenant": users_by_role.get(UserRole.tenant.value, 0),
                "landlord": users_by_role.get(UserRole.landlord.value, 0),
                "maintenance_worker": users_by_role.get(UserRole.maintenance_worker.value, 0),
            },
        },
        "bookings": {
            "total": sum(bookings_by_status.values()),
            "pending": bookings_by_status.get(BookingStatus.pending.value, 0),
            "paid": bookings_by_status.get(BookingStatus.paid.value, 0),
            "payment_review": bookings_by_status.get(BookingStatus.payment_review.value, 0),
        },
        "payments": {
            "total_count": sum(item["count"] for item in payments_by_status),
            "success_count": next((item["count"] for item in payments_by_status if item["status"] == PaymentStatus.success.value), 0),
            "success_amount_minor": next((item["settlement_amount_minor"] for item in payments_by_status if item["status"] == PaymentStatus.success.value), 0),
            "by_status": payments_by_status,
        },
        "notifications": {
            "failed_outbox": failed_notifications or 0,
        },
        "recent_logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in recent_logs
        ],
    }


@router.get("/system-alerts/schema")
async def get_system_alert_schema(
    _: User = Depends(require_admin),
) -> dict:
    return {
        "categories": ALERT_CATEGORIES,
        "detection_types": ALERT_DETECTION_TYPES,
        "record_retention_days": SYSTEM_ALERT_PROCESS_RECORD_RETENTION_DAYS,
        "record_detail_fields": ["报错内容", "运行详情", "系统说明"],
    }


@router.get("/system-alerts")
async def list_system_alerts(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    include_resolved: bool = Query(default=False),
    read_status: str = Query(default="unread", pattern="^(unread|read|all)$"),
) -> list[dict]:
    now = datetime.now(timezone.utc)
    alerts: list[dict] = []
    read_action_types = [
        "mark_alert_read",
        "mark_system_alert_read",
        "resolve_generated_alert",
        "resolve_generated_system_alert",
        "resolve_system_alert",
    ]
    read_alert_keys = set(await session.scalars(
        select(SystemAlertProcessRecord.alert_key).where(
            SystemAlertProcessRecord.action_type.in_(read_action_types)
        )
    ))

    persisted_stmt = select(PersistedSystemAlert).order_by(PersistedSystemAlert.updated_at.desc()).limit(60)
    if not include_resolved:
        persisted_stmt = persisted_stmt.where(PersistedSystemAlert.status != SystemAlertStatus.resolved)
    persisted_rows = await session.scalars(persisted_stmt)
    alerts.extend(_persisted_alert_to_card(row) for row in persisted_rows)

    missing_unit_type_rows = await session.scalars(
        select(UnitType)
        .options(selectinload(UnitType.institute))
        .where(
            UnitType.deleted_at.is_(None),
            or_(
                UnitType.image_urls.is_(None),
                UnitType.description.is_(None),
                UnitType.area_sqm.is_(None),
                UnitType.available_from.is_(None),
            ),
        )
        .order_by(UnitType.updated_at.desc())
        .limit(12)
    )
    for row in missing_unit_type_rows:
        missing_fields = []
        if not row.image_urls:
            missing_fields.append("户型图片")
        if not row.description:
            missing_fields.append("户型描述")
        if row.area_sqm is None:
            missing_fields.append("面积")
        if row.available_from is None:
            missing_fields.append("可入住日期")
        alerts.append({
            "id": f"unit_type_missing:{row.id}",
            "category": ALERT_CATEGORY_UNIT_TYPE,
            "severity": "medium",
            "title": "户型信息缺失",
            "summary": f"{row.name} 缺少 {', '.join(missing_fields) or '必要字段'}",
            "detail": f"公寓：{row.institute.name if row.institute else '-'}，缺失字段：{', '.join(missing_fields) or '无'}。",
            "source": "unit_type",
            "source_id": row.id,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "户型名称": row.name,
                    "公寓": row.institute.name if row.institute else None,
                    "缺失字段": missing_fields,
                    "图片数量": len(row.image_urls or []),
                    "描述": row.description,
                    "面积": row.area_sqm,
                    "可入住日期": row.available_from,
                },
                {"处理目标": "补齐户型图片、描述、面积、入住日期等字段"},
                "户型信息不完整会影响用户判断和 AI 推荐质量。",
            ),
            "action": None,
        })

    vacancy_conflict_rows = await session.scalars(
        select(UnitType)
        .options(selectinload(UnitType.institute))
        .where(
            UnitType.deleted_at.is_(None),
            or_(
                UnitType.available_count < 0,
                UnitType.available_count > UnitType.total_count,
                (UnitType.available_count <= 0) & (UnitType.has_vacancy.is_(True)),
                (UnitType.available_count <= 0) & (UnitType.status == UnitTypeStatus.available),
            ),
        )
        .order_by(UnitType.updated_at.desc())
        .limit(12)
    )
    for row in vacancy_conflict_rows:
        alerts.append({
            "id": f"unit_type_vacancy:{row.id}",
            "category": ALERT_CATEGORY_UNIT_TYPE,
            "severity": "high",
            "title": "户型余量状态冲突",
            "summary": f"{row.name} 的余量和可租状态不一致",
            "detail": f"总量：{row.total_count}，余量：{row.available_count}，是否有余量：{_plain_value(row.has_vacancy)}，状态：{row.status.value if hasattr(row.status, 'value') else row.status}。",
            "source": "unit_type",
            "source_id": row.id,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "户型名称": row.name,
                    "公寓": row.institute.name if row.institute else None,
                    "总库存": row.total_count,
                    "可租余量": row.available_count,
                    "是否显示有余量": row.has_vacancy,
                    "展示状态": row.status.value if hasattr(row.status, "value") else str(row.status),
                },
                {"处理目标": "修正库存、可租标识和展示状态"},
                "没有余量仍显示可出租会导致预约冲突。",
            ),
            "action": None,
        })

    missing_embedding_rows = await session.scalars(
        select(UnitType)
        .options(selectinload(UnitType.institute))
        .where(
            UnitType.deleted_at.is_(None),
            UnitType.status == UnitTypeStatus.available,
            or_(UnitType.embedding.is_(None), UnitType.embedding == ""),
        )
        .order_by(UnitType.updated_at.desc())
        .limit(12)
    )
    for row in missing_embedding_rows:
        alerts.append({
            "id": f"ai_embedding_missing:{row.id}",
            "category": ALERT_CATEGORY_AI,
            "severity": "medium",
            "title": "AI 检索索引缺失",
            "summary": f"{row.name} 可租但没有 AI 检索索引",
            "detail": "该户型可能无法被 AI 找房、智能推荐或语义检索命中。",
            "source": "unit_type",
            "source_id": row.id,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "户型名称": row.name,
                    "公寓": row.institute.name if row.institute else None,
                    "当前状态": row.status.value if hasattr(row.status, "value") else str(row.status),
                    "索引内容": "无",
                },
                {"处理目标": "重建 AI 检索索引"},
                "AI 检索方面异常：索引缺失或重建失败会影响推荐结果。",
            ),
            "action": None,
        })

    failed_embedding_rows = await session.scalars(
        select(EmbeddingJob)
        .where(
            or_(
                EmbeddingJob.status == EmbeddingJobStatus.failed,
                (EmbeddingJob.status == EmbeddingJobStatus.processing) & (EmbeddingJob.started_at < now - timedelta(minutes=30)),
            )
        )
        .order_by(EmbeddingJob.created_at.desc())
        .limit(12)
    )
    for row in failed_embedding_rows:
        is_stalled = row.status == EmbeddingJobStatus.processing
        alerts.append({
            "id": f"ai_embedding_job:{row.id}",
            "category": ALERT_CATEGORY_AI,
            "severity": "high" if row.status == EmbeddingJobStatus.failed else "medium",
            "title": "AI 检索索引重建失败" if row.status == EmbeddingJobStatus.failed else "AI 检索索引重建超时",
            "summary": f"索引任务 #{row.id} 当前状态：{row.status.value}",
            "detail": row.error_message or ("索引任务处理超过 30 分钟。" if is_stalled else "索引任务失败但没有返回明确错误。"),
            "source": "embedding_job",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": (row.completed_at or row.started_at or row.created_at).isoformat(),
            "extra": _alert_extra(
                {
                    "任务状态": row.status.value,
                    "户型ID": row.property_id,
                    "开始时间": row.started_at,
                    "完成时间": row.completed_at,
                    "错误原因": row.error_message or ("索引任务处理超过 30 分钟。" if is_stalled else "索引任务失败但没有返回明确错误。"),
                    "报错位置": f"embedding_jobs / {row.id}",
                },
                {"任务编号": row.id, "来源表": "embedding_jobs"},
                row.error_message or ("索引任务处理超过 30 分钟。" if is_stalled else "索引任务失败但没有返回明确错误。"),
            ),
            "action": None,
        })

    pending_review_rows = await session.scalars(
        select(Review)
        .options(selectinload(Review.institute))
        .where(
            Review.status == ReviewStatus.pending,
            Review.created_at < now - timedelta(hours=24),
        )
        .order_by(Review.created_at.asc())
        .limit(12)
    )
    for row in pending_review_rows:
        wait_hours = int((now - row.created_at).total_seconds() // 3600)
        alerts.append({
            "id": f"backoffice_review_delay:{row.id}",
            "category": ALERT_CATEGORY_BACKOFFICE,
            "severity": "medium" if wait_hours < 48 else "high",
            "title": "评价审核处理超时",
            "summary": f"评价 #{row.id} 已等待后台处理 {wait_hours} 小时",
            "detail": f"公寓：{row.institute.name if row.institute else '-'}，评分：{row.rating}，待审核超过 24 小时。",
            "source": "review",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "评价ID": row.id,
                    "公寓": row.institute.name if row.institute else None,
                    "租客ID": row.tenant_id,
                    "评分": row.rating,
                    "提交时间": row.created_at,
                    "等待时长": f"{wait_hours} 小时",
                },
                {"处理目标": "后台人员审核评价并给出通过或驳回结果"},
                "后台处理速度异常：用户提交内容长时间未被处理。",
            ),
            "action": None,
        })

    pending_institute_rows = await session.scalars(
        select(Institute)
        .where(
            Institute.status == InstituteStatus.pending,
            Institute.created_at < now - timedelta(hours=24),
        )
        .order_by(Institute.created_at.asc())
        .limit(12)
    )
    for row in pending_institute_rows:
        wait_hours = int((now - row.created_at).total_seconds() // 3600)
        alerts.append({
            "id": f"backoffice_institute_delay:{row.id}",
            "category": ALERT_CATEGORY_BACKOFFICE,
            "severity": "medium" if wait_hours < 48 else "high",
            "title": "公寓资料审核处理超时",
            "summary": f"{row.name} 已等待后台审核 {wait_hours} 小时",
            "detail": "公寓资料提交后超过 24 小时仍未完成审核，会影响房源上线和后续运营。",
            "source": "institute",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "公寓ID": row.id,
                    "公寓名称": row.name,
                    "城市": row.city,
                    "创建人ID": row.created_by,
                    "提交时间": row.created_at,
                    "等待时长": f"{wait_hours} 小时",
                },
                {"处理目标": "后台人员完成公寓资料审核"},
                "后台处理速度异常：公寓资料审核队列处理过慢。",
            ),
            "action": None,
        })

    stalled_import_rows = await session.scalars(
        select(DataImport)
        .where(
            DataImport.status.in_([ImportStatus.pending, ImportStatus.processing]),
            DataImport.updated_at < now - timedelta(hours=2),
        )
        .order_by(DataImport.updated_at.asc())
        .limit(12)
    )
    for row in stalled_import_rows:
        wait_minutes = int((now - row.updated_at).total_seconds() // 60)
        alerts.append({
            "id": f"backoffice_import_delay:{row.id}",
            "category": ALERT_CATEGORY_BACKOFFICE,
            "severity": "medium" if wait_minutes < 360 else "high",
            "title": "数据导入处理超时",
            "summary": f"导入任务 #{row.id} 已停留 {wait_minutes} 分钟",
            "detail": f"来源：{row.source_name}，当前进度：成功 {row.success_records} / 总数 {row.total_records}。",
            "source": "data_import",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "导入任务ID": row.id,
                    "来源名称": row.source_name,
                    "来源类型": row.source_type.value,
                    "任务状态": row.status.value,
                    "总记录数": row.total_records,
                    "成功记录数": row.success_records,
                    "失败记录数": row.failed_records,
                    "最后更新时间": row.updated_at,
                    "停留时长": f"{wait_minutes} 分钟",
                },
                {"处理目标": "后台人员检查导入任务是否卡住并补处理失败记录"},
                "后台处理速度异常：信息导入或录入处理长时间没有推进。",
            ),
            "action": None,
        })

    failed_outbox_rows = await session.scalars(
        select(NotificationOutbox)
        .where(NotificationOutbox.status == NotificationOutboxStatus.failed)
        .order_by(NotificationOutbox.updated_at.desc())
        .limit(20)
    )
    for row in failed_outbox_rows:
        alerts.append({
            "id": f"notification:{row.id}",
            "category": ALERT_CATEGORY_SYSTEM_API,
            "severity": "high" if row.attempts >= 3 else "medium",
            "title": "通知发送失败",
            "summary": f"{row.event_type} 发送失败，已尝试 {row.attempts} 次",
            "detail": row.last_error or "通知投递失败，等待管理员检查或重试。",
            "source": "notification_outbox",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "通知类型": row.event_type,
                    "发送状态": row.status.value,
                    "尝试次数": row.attempts,
                    "收件人": row.recipient_email,
                    "错误原因": row.last_error or "通知服务未返回明确错误。",
                    "报错位置": f"notification_outbox / {row.id}",
                },
                {"通知编号": row.id, "来源表": "notification_outbox"},
                row.last_error or "通知服务未返回明确错误。",
            ),
            "action": None,
        })

    overdue_booking_rows = await session.scalars(
        select(Booking)
        .where(
            Booking.status == BookingStatus.pending,
            Booking.created_at < now - timedelta(hours=2),
        )
        .order_by(Booking.created_at.asc())
        .limit(12)
    )
    for row in overdue_booking_rows:
        alerts.append({
            "id": f"booking_pending:{row.id}",
            "category": ALERT_CATEGORY_BOOKING,
            "severity": "high",
            "title": "预约待处理超时",
            "summary": f"预约 #{row.id} 超过 2 小时仍未处理",
            "detail": f"租客用户 ID：{row.user_id}，户型 ID：{row.unit_type_id or '-'}，预计入住：{row.scheduled_date or '-'}。",
            "source": "booking",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "预约状态": row.status.value,
                    "租客用户ID": row.user_id,
                    "户型ID": row.unit_type_id,
                    "对接人员ID": row.bm_id,
                    "创建时间": row.created_at.isoformat(),
                },
                {"处理目标": "分配对接人员并联系租客"},
                "预约链路超过 2 小时没有进入后续处理。",
            ),
            "action": None,
        })

    payment_review_booking_rows = await session.scalars(
        select(Booking)
        .where(
            Booking.status == BookingStatus.payment_review,
            Booking.updated_at < now - timedelta(hours=2),
        )
        .order_by(Booking.updated_at.asc())
        .limit(12)
    )
    for row in payment_review_booking_rows:
        alerts.append({
            "id": f"booking_payment_review:{row.id}",
            "category": ALERT_CATEGORY_ORDER,
            "severity": "high",
            "title": "订单支付待人工核验",
            "summary": f"订单 #{row.id} 已进入支付核验超过 2 小时",
            "detail": "需要核对支付流水、订单金额与合同状态，避免租客订单卡在待确认状态。",
            "source": "booking",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "订单状态": row.status.value,
                    "订金状态": row.deposit_status,
                    "支付流水": row.payment_transaction_id,
                    "更新时间": row.updated_at.isoformat(),
                },
                {"处理目标": "核对支付流水、订单金额和合同状态"},
                "订单在支付/订金确认环节卡住。",
            ),
            "action": None,
        })

    expired_payment_booking_rows = await session.scalars(
        select(Booking)
        .where(
            Booking.status.in_([BookingStatus.payment_pending, BookingStatus.payment_processing]),
            Booking.payment_expires_at.is_not(None),
            Booking.payment_expires_at < now,
        )
        .order_by(Booking.payment_expires_at.asc())
        .limit(12)
    )
    for row in expired_payment_booking_rows:
        alerts.append({
            "id": f"booking_payment_expired:{row.id}",
            "category": ALERT_CATEGORY_ORDER,
            "severity": "medium",
            "title": "支付窗口已过期但订单未关闭",
            "summary": f"订单 #{row.id} 支付有效期已过",
            "detail": f"过期时间：{row.payment_expires_at.isoformat() if row.payment_expires_at else '-'}，当前状态：{row.status.value}。",
            "source": "booking",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "订单状态": row.status.value,
                    "支付过期时间": row.payment_expires_at.isoformat() if row.payment_expires_at else None,
                    "库存锁定": row.inventory_reserved,
                    "错误原因": "支付有效期已过，但订单仍处于待支付链路，未自动关闭或释放库存。",
                    "报错位置": f"bookings / {row.id}",
                },
                {"预约编号": row.id, "来源表": "bookings"},
                "支付有效期已过，但订单仍处于待支付链路，未自动关闭或释放库存。",
            ),
            "action": None,
        })

    failed_payment_rows = await session.scalars(
        select(Payment)
        .where(Payment.status.in_([PaymentStatus.failed, PaymentStatus.review, PaymentStatus.refund_pending]))
        .order_by(Payment.updated_at.desc())
        .limit(12)
    )
    for row in failed_payment_rows:
        severity = "high" if row.status in (PaymentStatus.review, PaymentStatus.refund_pending) else "medium"
        title = {
            PaymentStatus.failed: "支付失败记录待查看",
            PaymentStatus.review: "支付流水待复核",
            PaymentStatus.refund_pending: "退款待处理",
        }.get(row.status, "支付异常")
        alerts.append({
            "id": f"payment:{row.id}",
            "category": ALERT_CATEGORY_ORDER,
            "severity": severity,
            "title": title,
            "summary": f"支付单 {row.order_id} 当前状态：{row.status.value}",
            "detail": row.trade_state_desc or f"金额：{row.amount}，预约 ID：{row.booking_id}，支付方式：{row.payment_method}。",
            "source": "payment",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "支付状态": row.status.value,
                    "订单号": row.order_id,
                    "预约ID": row.booking_id,
                    "金额": row.amount,
                    "支付方式": row.payment_method,
                    "接口状态": row.trade_state,
                    "接口说明": row.trade_state_desc,
                },
                {"处理目标": "核对支付、订金或退款状态"},
                "支付/订金/退款链路存在失败、复核或待处理状态。",
            ),
            "action": None,
        })

    pending_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status.in_([RepairStatus.pending, RepairStatus.pending_escalated]),
            RepairRequest.updated_at < now - timedelta(hours=4),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in pending_repair_rows:
        alerts.append({
            "id": f"repair_pending:{row.id}",
            "category": ALERT_CATEGORY_AFTER_SALES,
            "severity": "high",
            "title": "维修工单待派单超时",
            "summary": f"工单 #{row.id} 超过 4 小时未派单",
            "detail": f"问题类型：{row.issue_type.value}，租客 ID：{row.tenant_id}，负责人 ID：{row.bm_id}。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "维修状态": row.status.value,
                    "问题类型": row.issue_type.value,
                    "租客ID": row.tenant_id,
                    "负责人ID": row.bm_id,
                    "维修工ID": row.assigned_worker_id,
                },
                {"处理目标": "分配维修工并联系租客"},
                "售后维修长时间无人处理或无人确认。",
            ),
            "action": None,
        })

    assigned_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status == RepairStatus.assigned,
            RepairRequest.updated_at < now - timedelta(hours=24),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in assigned_repair_rows:
        alerts.append({
            "id": f"repair_assigned:{row.id}",
            "category": ALERT_CATEGORY_AFTER_SALES,
            "severity": "medium",
            "title": "维修已派单但未开工",
            "summary": f"工单 #{row.id} 已派单超过 24 小时",
            "detail": f"维修工用户 ID：{row.assigned_worker_id or '-'}，计划时间：{row.scheduled_time or '-'}。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "维修状态": row.status.value,
                    "维修工ID": row.assigned_worker_id,
                    "计划时间": row.scheduled_time,
                    "最近更新时间": row.updated_at.isoformat(),
                },
                {"处理目标": "确认维修工是否已联系并开工"},
                "维修已派单但没有进入开工节点。",
            ),
            "action": None,
        })

    stalled_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status == RepairStatus.in_progress,
            RepairRequest.updated_at < now - timedelta(hours=48),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in stalled_repair_rows:
        alerts.append({
            "id": f"repair_stalled:{row.id}",
            "category": ALERT_CATEGORY_AFTER_SALES,
            "severity": "high",
            "title": "维修进度停滞",
            "summary": f"工单 #{row.id} 维修中超过 48 小时未更新",
            "detail": f"维修工用户 ID：{row.assigned_worker_id or '-'}，最近记录：{row.work_record or '暂无维修记录'}。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "维修状态": row.status.value,
                    "维修工ID": row.assigned_worker_id,
                    "最近维修记录": row.work_record,
                    "维修图片": row.work_images,
                },
                {"处理目标": "要求维修工提交进度、原因、图片或材料"},
                "维修中超过 48 小时没有进度更新。",
            ),
            "action": None,
        })

    completed_unconfirmed_repair_rows = await session.scalars(
        select(RepairRequest)
        .where(
            RepairRequest.status == RepairStatus.completed,
            RepairRequest.updated_at < now - timedelta(hours=48),
        )
        .order_by(RepairRequest.updated_at.asc())
        .limit(12)
    )
    for row in completed_unconfirmed_repair_rows:
        alerts.append({
            "id": f"repair_unconfirmed:{row.id}",
            "category": ALERT_CATEGORY_AFTER_SALES,
            "severity": "low",
            "title": "维修完成待租客确认",
            "summary": f"工单 #{row.id} 完成超过 48 小时未确认",
            "detail": "需要提醒租客确认维修结果，或由管理员核实后结案。",
            "source": "repair_request",
            "source_id": row.id,
            "status": row.status.value,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "维修状态": row.status.value,
                    "完成时间": row.completed_at,
                    "确认状态": row.status.value,
                },
                {"处理目标": "提醒租客确认或管理员核实结案"},
                "维修完成后长时间没有确认结果。",
            ),
            "action": None,
        })

    contract_pdf_failed_rows = await session.scalars(
        select(Contract)
        .where(Contract.pdf_status == "failed")
        .order_by(Contract.updated_at.desc())
        .limit(12)
    )
    for row in contract_pdf_failed_rows:
        alerts.append({
            "id": f"contract_pdf:{row.id}",
            "category": ALERT_CATEGORY_CONTRACT,
            "severity": "high",
            "title": "合同 PDF 生成失败",
            "summary": f"合同 {row.agreement_number or row.id} 无法生成签署文件",
            "detail": row.pdf_last_error or "PDF 生成服务未返回明确错误。",
            "source": "contract",
            "source_id": row.id,
            "status": row.pdf_status,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "合同编号": row.agreement_number,
                    "合同状态": row.status,
                    "PDF状态": row.pdf_status,
                    "错误原因": row.pdf_last_error or "PDF 生成服务未返回明确错误。",
                    "报错位置": f"contracts / {row.id}",
                },
                {"合同ID": row.id, "来源表": "contracts"},
                row.pdf_last_error or "PDF 生成服务未返回明确错误。",
            ),
            "action": None,
        })

    unsigned_contract_rows = await session.scalars(
        select(Contract)
        .where(
            Contract.status == "generated",
            Contract.updated_at < now - timedelta(hours=24),
        )
        .order_by(Contract.updated_at.asc())
        .limit(12)
    )
    for row in unsigned_contract_rows:
        alerts.append({
            "id": f"contract_unsigned:{row.id}",
            "category": ALERT_CATEGORY_CONTRACT,
            "severity": "medium",
            "title": "合同生成后未签署",
            "summary": f"合同 {row.agreement_number or row.id} 超过 24 小时未签署",
            "detail": f"预约 ID：{row.booking_id}，租客用户 ID：{row.tenant_id}，模板：{row.template_name}。",
            "source": "contract",
            "source_id": row.id,
            "status": row.status,
            "updated_at": row.updated_at.isoformat(),
            "extra": _alert_extra(
                {
                    "合同编号": row.agreement_number,
                    "合同状态": row.status,
                    "预约ID": row.booking_id,
                    "租客ID": row.tenant_id,
                    "模板": row.template_name,
                },
                {"处理目标": "提醒用户签署或检查用户填写字段"},
                "合同生成后未签，可能存在字段缺失、用户填写异常或签署入口问题。",
            ),
            "action": None,
        })

    for item in provider_availability():
        if not item.available and not item.test_mode:
            alerts.append({
                "id": f"payment_provider:{item.method.value}",
                "category": ALERT_CATEGORY_SYSTEM_API,
                "severity": "medium",
                "title": "支付接口未开通",
                "summary": f"{item.method.value} 当前不可用",
                "detail": item.reason or "支付服务商配置缺失或尚未完成联调。",
                "source": "payment_provider",
                "source_id": item.method.value,
                "status": "unavailable",
                "updated_at": now.isoformat(),
                "extra": _alert_extra(
                    {
                        "接口名称": item.method.value,
                        "可用状态": item.available,
                        "测试模式": item.test_mode,
                        "异常原因": item.reason or "支付接口不可用。",
                        "报错位置": f"payment_provider / {item.method.value}",
                    },
                    {"来源": "provider_availability", "接口": item.method.value},
                    item.reason or "支付接口不可用。",
                ),
                "action": None,
            })

    runtime_event_rows = await session.scalars(
        select(RuntimeEvent)
        .where(
            RuntimeEvent.handled_at.is_(None),
            or_(RuntimeEvent.status_code >= 500, RuntimeEvent.level.in_(["ERROR", "CRITICAL"])),
        )
        .order_by(RuntimeEvent.created_at.desc())
        .limit(20)
    )
    for row in runtime_event_rows:
        alerts.append({
            "id": f"runtime_event:{row.id}",
            "category": ALERT_CATEGORY_SYSTEM_API,
            "severity": "high" if (row.status_code or 0) >= 500 else "medium",
            "title": row.title,
            "summary": row.message or "后端运行异常已写入运行事件表。",
            "detail": f"接口：{row.method or '-'} {row.path or '-'}，请求编号：{row.request_id or '-'}。",
            "source": "runtime_event",
            "source_id": row.id,
            "status": "open",
            "updated_at": row.created_at.isoformat(),
            "extra": _alert_extra(
                {
                    "错误类型": row.event_type,
                    "接口路径": row.path,
                    "请求方法": row.method,
                    "HTTP状态码": row.status_code,
                    "请求编号": row.request_id,
                    "报错内容": row.message,
                    "报错位置": f"runtime_events / {row.id}",
                },
                {"运行附加信息": row.extra or "无", "来源表": "runtime_events"},
                row.message,
            ),
            "action": None,
        })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    category_order = {
        ALERT_CATEGORY_SYSTEM_API: 0,
        ALERT_CATEGORY_AI: 1,
        ALERT_CATEGORY_ORDER: 2,
        ALERT_CATEGORY_CONTRACT: 3,
        ALERT_CATEGORY_AFTER_SALES: 4,
        ALERT_CATEGORY_BOOKING: 5,
        ALERT_CATEGORY_UNIT_TYPE: 6,
    }
    for item in alerts:
        _ensure_alert_extra(item)
        if not str(item["id"]).startswith("system:") and not item.get("action"):
            item["action"] = _generated_alert_action(item)
    allowed_prefixes = (
        "ai_embedding_job:",
        "booking_payment_expired:",
        "contract_pdf:",
        "notification:",
        "payment_provider:",
        "runtime_event:",
        "system:",
    )
    alerts = [item for item in alerts if str(item["id"]).startswith(allowed_prefixes)]
    for item in alerts:
        item["read"] = str(item["id"]) in read_alert_keys
        item["location"] = f"{item.get('source') or '-'} / {item.get('source_id') or '-'}"
    if read_status == "unread":
        alerts = [item for item in alerts if not item["read"]]
    elif read_status == "read":
        alerts = [item for item in alerts if item["read"]]
    alerts.sort(
        key=lambda item: (
            category_order.get(item.get("category"), 99),
            severity_order.get(item["severity"], 9),
            item["updated_at"],
        ),
        reverse=False,
    )
    return alerts[:60]


@router.post("/system-alerts", status_code=status.HTTP_201_CREATED)
async def create_system_alert(
    body: SystemAlertCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    alert = PersistedSystemAlert(
        category=body.category,
        severity=SystemAlertSeverity(body.severity),
        title=body.title,
        summary=body.summary,
        detail=body.detail,
        source=body.source,
        source_id=body.source_id,
        status=SystemAlertStatus.open,
        action_type=body.action_type or "resolve_system_alert",
        action_label=body.action_label or "标为已读",
        action_resource_id=body.action_resource_id,
        extra=body.extra,
        reported_by_id=current_user.id,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return _persisted_alert_to_card(alert)


@router.get("/system-alerts/records")
async def list_system_alert_process_records(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    alert_key: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    limit: int = Query(default=80, ge=1, le=200),
) -> list[dict]:
    deleted_count = await purge_expired_alert_process_records(session)
    if deleted_count:
        await session.commit()

    stmt = select(SystemAlertProcessRecord).order_by(SystemAlertProcessRecord.created_at.desc()).limit(limit)
    if alert_key:
        stmt = stmt.where(SystemAlertProcessRecord.alert_key == alert_key)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(
            SystemAlertProcessRecord.alert_key.ilike(pattern),
            SystemAlertProcessRecord.title.ilike(pattern),
            SystemAlertProcessRecord.source.ilike(pattern),
            SystemAlertProcessRecord.source_id.ilike(pattern),
            SystemAlertProcessRecord.note.ilike(pattern),
        ))
    if category:
        stmt = stmt.where(SystemAlertProcessRecord.category == category)
    if action_type:
        stmt = stmt.where(SystemAlertProcessRecord.action_type == action_type)
    if source:
        stmt = stmt.where(SystemAlertProcessRecord.source == source)
    if source_id:
        stmt = stmt.where(SystemAlertProcessRecord.source_id == source_id)
    rows = await session.scalars(stmt)
    return [
        {
            "id": row.id,
            "alert_key": row.alert_key,
            "system_alert_id": row.system_alert_id,
            "category": row.category,
            "severity": row.severity,
            "title": row.title,
            "source": row.source,
            "source_id": row.source_id,
            "action_type": row.action_type,
            "note": row.note,
            "status_before": row.status_before,
            "status_after": row.status_after,
            "handled_by_id": row.handled_by_id,
            "extra": _process_record_extra(row),
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.patch("/system-alerts/generated/read")
async def mark_generated_system_alert_read(
    body: GeneratedSystemAlertResolveRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    action_type = "mark_alert_read"
    record = await record_alert_action(
        session,
        current_user,
        alert_key=body.alert_key,
        category=body.category,
        severity=body.severity,
        title=body.title,
        source=body.source,
        source_id=body.source_id,
        action_type=action_type,
        note=body.note or "已读",
        status_before=None,
        status_after=None,
        extra=body.extra or _alert_extra(
            {"类型": body.category, "位置": f"{body.source} / {body.source_id or '-'}"},
            {"阅读状态": "已读"},
            body.detail,
        ),
    )
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "alert_key": record.alert_key, "read": True}


@router.patch("/system-alerts/{alert_id}/read")
async def mark_system_alert_read(
    alert_id: int,
    body: SystemAlertResolveRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    alert = await session.get(PersistedSystemAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="System alert not found")
    alert.status = SystemAlertStatus.acknowledged
    record = await record_alert_action(
        session,
        current_user,
        alert_key=f"system:{alert.id}",
        category=alert.category,
        severity=alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
        title=alert.title,
        source=alert.source,
        source_id=alert.source_id or alert.id,
        action_type="mark_system_alert_read",
        note=(body.note if body else None) or "已读",
        status_before=None,
        status_after=None,
        system_alert_id=alert.id,
        extra=_alert_extra(
            {"类型": alert.category, "位置": f"{alert.source} / {alert.source_id or alert.id}"},
            {"阅读状态": "已读"},
            alert.detail or alert.summary,
        ),
    )
    await session.commit()
    await session.refresh(record)
    return {"id": alert.id, "read": True}


@router.patch("/system-alerts/generated/resolve")
async def resolve_generated_system_alert(
    body: GeneratedSystemAlertResolveRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    record = await record_alert_action(
        session,
        current_user,
        alert_key=body.alert_key,
        category=body.category,
        severity=body.severity,
        title=body.title,
        source=body.source,
        source_id=body.source_id,
        action_type=body.action_type or (
            "resolve_generated_system_alert"
            if _is_generated_system_alert(
                body.category,
                alert_key=body.alert_key,
                source=body.source,
                title=body.title,
            )
            else "resolve_generated_alert"
        ),
        note=body.note,
        status_before=None,
        status_after=None,
        extra=body.extra or _alert_extra(
            {"异常状态": body.status, "来源": body.source, "编号": body.source_id},
            {"处理结果": "管理员已处理"},
            body.detail,
        ),
    )
    if body.source == "runtime_event" and body.source_id:
        await session.execute(
            update(RuntimeEvent)
            .where(RuntimeEvent.id == int(body.source_id))
            .values(handled_at=datetime.now(timezone.utc))
        )
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "alert_key": record.alert_key, "status": "resolved"}


@router.patch("/system-alerts/{alert_id}/resolve")
async def resolve_system_alert(
    alert_id: int,
    body: SystemAlertResolveRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    alert = await session.get(PersistedSystemAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="System alert not found")
    details = alert.extra or {}
    if body and body.note:
        details["resolve_note"] = body.note
    alert.extra = details or None
    status_before = alert.status.value if hasattr(alert.status, "value") else str(alert.status)
    alert.mark_resolved(current_user.id)
    await record_alert_action(
        session,
        current_user,
        alert_key=f"system:{alert.id}",
        system_alert_id=alert.id,
        category=alert.category,
        severity=alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
        title=alert.title,
        source=alert.source,
        source_id=alert.source_id or alert.id,
        action_type="resolve_system_alert",
        note=body.note if body else None,
        status_before=None,
        status_after=None,
        extra=details or _alert_extra(
            {"异常状态": status_before, "来源": alert.source, "编号": alert.source_id or alert.id},
            {"处理结果": alert.status.value},
            alert.detail,
        ),
    )
    await session.commit()
    return {"id": alert.id, "status": alert.status.value}


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_landlord),
) -> dict:
    return await StatsService(session).get_stats()


@router.get("/logs")
async def list_audit_logs(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
) -> list[dict]:
    logs = await AuditService(session).list_logs(
        skip=skip,
        limit=limit,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        keyword=keyword,
        start_at=start_at,
        end_at=end_at,
    )
    unit_type_ids = {
        log.resource_id
        for log in logs
        if log.resource_type == "unit_type" and log.resource_id is not None
    }
    unit_types: dict[int, UnitType] = {}
    if unit_type_ids:
        result = await session.scalars(
            select(UnitType)
            .options(selectinload(UnitType.institute))
            .where(UnitType.id.in_(unit_type_ids))
        )
        unit_types = {unit_type.id: unit_type for unit_type in result.all()}

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": _audit_details(log, unit_types),
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.post("/unit-types/{unit_type_id}/review")
async def review_unit_type(
    unit_type_id: int,
    body: UnitTypeReviewRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    valid_results = {"normal", "abnormal"}
    if body.result not in valid_results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid result. Must be one of: {valid_results}",
        )

    unit_type = await UnitTypeService(session).get(unit_type_id)
    if not unit_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit type not found")

    await AuditService(session).create_log(
        user_id=current_user.id,
        action="unit_type_review",
        resource_type="unit_type",
        resource_id=unit_type_id,
        details={
            "table": "unit_types",
            "unit_type_id": unit_type_id,
            "result": body.result,
            "note": body.note,
            "unit_type_name": unit_type.name,
            "institute_table": "institutes",
            "institute_id": unit_type.institute_id,
            "institute_name": unit_type.institute.name if unit_type.institute else None,
            "current_status": unit_type.status.value if hasattr(unit_type.status, "value") else str(unit_type.status),
        },
    )
    return {"detail": "Unit type review recorded", "id": unit_type_id, "result": body.result}


@router.patch("/unit-types/{unit_type_id}/status")
async def update_unit_type_status(
    unit_type_id: int,
    new_status: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    valid_statuses = {"available", "rented", "maintenance"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    unit_type = await UnitTypeService(session).update(
        unit_type_id, UnitTypeUpdate(status=new_status)
    )
    if not unit_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit type not found")

    await AuditService(session).create_log(
        user_id=current_user.id,
        action="unit_type_status_change",
        resource_type="unit_type",
        resource_id=unit_type_id,
        details={
            "table": "unit_types",
            "unit_type_id": unit_type_id,
            "new_status": new_status,
            "unit_type_name": unit_type.name,
            "institute_table": "institutes",
            "institute_id": unit_type.institute_id,
            "institute_name": unit_type.institute.name if unit_type.institute else None,
        },
    )
    return {"detail": f"Unit type {unit_type_id} status set to {new_status}"}


@router.get("/logs/resource")
async def list_audit_logs_by_resource(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    resource_type: str = Query(...),
    resource_id: int = Query(...),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    """按资源类型+ID查询审计日志（资源修改历史）"""
    logs = await AuditService(session).list_logs(
        skip=skip, limit=limit,
        resource_type=resource_type, resource_id=resource_id,
    )
    unit_types: dict[int, UnitType] = {}
    if resource_type == "unit_type":
        unit_type = await session.scalar(
            select(UnitType)
            .options(selectinload(UnitType.institute))
            .where(UnitType.id == resource_id)
        )
        if unit_type:
            unit_types[unit_type.id] = unit_type

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": _audit_details(log, unit_types),
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.patch("/properties/{property_id}/status")
async def moderate_property(
    property_id: int,
    new_status: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    valid_statuses = {"available", "rented", "maintenance", "offline", "pending_review"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    from app.schemas.property import PropertyUpdate

    property_obj = await PropertyService(session).update(
        property_id, PropertyUpdate(status=new_status)
    )
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    await AuditService(session).create_log(
        user_id=current_user.id,
        action="property_moderate",
        resource_type="property",
        resource_id=property_id,
        details={"new_status": new_status},
    )
    return {"detail": f"Property {property_id} status set to {new_status}"}


@router.get("/embeddings/stats")
async def get_embedding_stats(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    return await EmbeddingJobService(session).get_stats()


@router.post("/embeddings/reindex")
async def trigger_embedding_reindex(
    property_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    result = await EmbeddingJobService(session).trigger_reindex(property_id)
    await AuditService(session).create_log(
        user_id=current_user.id,
        action="embedding_reindex",
        resource_type="unit_type" if property_id else "embedding",
        resource_id=property_id,
        details={"scope": "single" if property_id else "all", "result": result},
    )
    return result


@router.patch("/users/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: int,
    new_role: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> UserRead:
    if new_role not in {"tenant", "landlord", "admin", "maintenance_worker"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be: tenant, landlord, maintenance_worker, or admin",
        )

    from app.schemas.user import UserUpdate

    user = await UserService(session).update(user_id, UserUpdate(role=UserRole(new_role)))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await AuditService(session).create_log(
        user_id=current_user.id,
        action="user_role_change",
        resource_type="user",
        resource_id=user_id,
        details={"new_role": new_role},
    )
    return user




@router.get("/landlord-workers-status")
async def get_landlord_workers_status(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Admin查看各房东的维修工状态（Yes/No看板）"""
    from app.models.repair import RepairWorker, WorkerScope, WorkerStatus

    # 获取所有房东
    landlord_stmt = select(User).where(User.role == UserRole.landlord, User.status == "active")
    landlord_result = await session.execute(landlord_stmt)
    landlords = landlord_result.scalars().all()

    result = []
    for ll in landlords:
        # 该房东的apt工人
        workers_stmt = (
            select(RepairWorker)
            .where(
                (RepairWorker.manager_id == ll.id) &
                (RepairWorker.scope == WorkerScope.apartment)
            )
        )
        worker_result = await session.execute(workers_stmt)
        workers = worker_result.scalars().all()

        available_count = sum(1 for w in workers if w.status == WorkerStatus.available)

        result.append({
            "landlord_id": ll.id,
            "landlord_name": ll.username,
            "has_workers": len(workers) > 0,
            "worker_count": len(workers),
            "available_count": available_count,
        })

    return result

"""通知 API 路由 — 消息中心、铃铛、投递记录及测试场景"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.models.notification import NotificationEventType
from app.schemas.notification import (
    NotificationRead,
    UnreadCount,
    MarkAllReadResponse,
    DeliveryRecordRead,
    TestScenarioRequest,
    TestScenarioResponse,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter()


# ── 站内通知 CRUD ─────────────────────────────────────────────

@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    filter: str | None = Query(None, description="all | unread"),
    entity_type: str | None = Query(None, description="按实体类型筛选"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[NotificationRead]:
    """获取当前用户的通知列表，支持按已读状态和实体类型筛选。"""
    return await NotificationService(session).list_by_user(
        current_user.id, filter_type=filter, entity_type=entity_type,
    )


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UnreadCount:
    """获取未读通知数量（铃铛角标）。"""
    count = await NotificationService(session).get_unread_count(current_user.id)
    return UnreadCount(count=count)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> NotificationRead:
    """标记单条通知为已读。"""
    notification = await NotificationService(session).mark_read(notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return notification


@router.patch("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MarkAllReadResponse:
    """标记所有未读通知为已读。"""
    affected = await NotificationService(session).mark_all_read(current_user.id)
    return MarkAllReadResponse(affected=affected)


# ── 投递记录 ──────────────────────────────────────────────────

@router.get("/deliveries/{delivery_id}", response_model=DeliveryRecordRead)
async def get_delivery(
    delivery_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> DeliveryRecordRead:
    """获取单条投递记录详情。"""
    delivery = await NotificationService(session).get_delivery(delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
    if delivery.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return delivery


# ════════════════════════════════════════════════════════════════
# 测试场景触发（开发/调试用）
# ════════════════════════════════════════════════════════════════

# 所有可用场景
AVAILABLE_SCENARIOS = sorted(e.value for e in NotificationEventType)


@router.get("/test-scenarios", response_model=list[str])
async def list_test_scenarios(
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """列出所有可用于测试的通知场景。"""
    return AVAILABLE_SCENARIOS


# 场景键别名（前端短key ↔ 后端枚举值）
SCENARIO_ALIASES = {
    "payment_expiring_3h": "payment_expiring_in_3_hours",
}


@router.post("/test-trigger", response_model=TestScenarioResponse)
async def trigger_test_scenario(
    body: TestScenarioRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> TestScenarioResponse:
    """触发一个测试通知场景。"""
    # 解析别名
    scenario = SCENARIO_ALIASES.get(body.scenario, body.scenario)

    if scenario not in AVAILABLE_SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知场景: {body.scenario}。可用场景: {AVAILABLE_SCENARIOS}",
        )

    target_user_id = body.user_id or current_user.id
    target_order_id = body.order_id
    target_property_id = body.property_id

    # 场景上下文 — 填充模拟数据用于模板
    scenario_context = _build_scenario_context(scenario)

    svc = NotificationService(session)
    result = await svc.dispatch_event(
        event_type=scenario,
        user_id=target_user_id,
        order_id=target_order_id,
        property_id=target_property_id,
        entity_type="order",
        entity_id=str(target_order_id) if target_order_id else None,
        context_extra=scenario_context,
    )

    logger.info(
        "测试场景 [%s] 已触发: user=%s notification=%s deliveries=%s channels=%s",
        scenario, target_user_id,
        result["notification_id"], result["delivery_ids"], result["channels_sent"],
    )

    return TestScenarioResponse(
        scenario=body.scenario,
        notification_id=result["notification_id"],
        delivery_ids=result["delivery_ids"],
        channels_sent=result["channels_sent"],
        detail=f"场景 '{body.scenario}' 已触发，渠道: {result['channels_sent']}。"
                f"跳过的渠道: {[s['channel'] for s in result.get('skipped', [])]}",
    )


# ── 辅助函数 ──────────────────────────────────────────────────

def _build_scenario_context(scenario: str) -> dict:
    """为测试场景构建模拟上下文数据。"""
    base = {
        "user_name": "测试用户",
        "tenant_name": "测试租客",
        "landlord_name": "测试房东",
        "order_number": f"ORD-{scenario[:8].upper()}-001",
        "property_name": "阳光花园A栋301",
        "property_short_name": "阳光花园A301",
        "property_city": "苏州",
        "property_address": "苏州市工业园区仁爱路111号",
        "lease_start_date": "2026-08-01",
        "lease_end_date": "2027-07-31",
        "lease_months": 12,
        "settlement_amount": "5000.00",
        "amount": "5000.00",
        "settlement_currency": "CNY",
        "currency": "CNY",
        "expires_at": "2026-07-23 23:59:59",
        "localized_expires_at": "2026年7月23日 23:59",
        "timezone": "Asia/Shanghai",
        "secure_order_url": "http://localhost:5173/order/1",
        "order_url": "http://localhost:5173/order/1",
        "payment_time": "2026-07-23 20:30:00",
        "contract_id": "CT-2026-001",
    }
    return base

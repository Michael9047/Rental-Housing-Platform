"""支付订单、托管测试收银台及验签 webhook 路由。"""
import json
import uuid
from decimal import Decimal
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_tenant
from app.core.config import get_settings
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.payment import (
    PaymentCreate, PaymentEligibilityResponse, PaymentMethodAvailability,
    PaymentResponse, PaymentResultResponse, TenantOrderDetail, TenantOrderListResponse,
)
from app.models.property_image import PropertyImage
from app.services.payment_provider import (
    AlipayProvider, CardCheckoutProvider, MockHostedPaymentProvider,
    ProviderUnavailableError, WeChatPayProvider, provider_availability,
)
from app.services.payment_service import PaymentOrderService

router = APIRouter()


SAFE_FAILURE_MESSAGES = {
    "payment_failed": "支付服务商未确认付款成功，可在有效期内重试。",
    "payment_expired": "超过24小时未完成支付。",
    "payment_review": "付款时间或回调信息异常，平台正在人工核对。",
    "refund_pending": "异常付款正在安排退款。",
}


def _can_view_payment(payment: Payment, current_user: User) -> bool:
    return payment.user_id == current_user.id or current_user.role == UserRole.admin


def _raise(exc: Exception) -> None:
    codes = {LookupError: 404, PermissionError: 403, TimeoutError: 410, RuntimeError: 409, ValueError: 400}
    raise HTTPException(status_code=codes.get(type(exc), 400), detail=str(exc))


@router.get("/orders/my", response_model=TenantOrderListResponse)
async def list_my_orders(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> TenantOrderListResponse:
    from app.services.tenant_order_service import TenantOrderService
    items = await TenantOrderService(session).list_for_tenant(current_user.id)
    return TenantOrderListResponse(items=items, total=len(items))


@router.get("/orders/my/{booking_id}", response_model=TenantOrderDetail)
async def get_my_order(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> TenantOrderDetail:
    from app.services.tenant_order_service import TenantOrderService
    try:
        return await TenantOrderService(session).detail_for_tenant(booking_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/orders/my/{booking_id}/validate-payment", response_model=PaymentEligibilityResponse)
async def validate_my_order_payment(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> PaymentEligibilityResponse:
    """进入收银台前由服务端重新核对归属、合同、库存、期限和金额。"""
    from app.services.tenant_order_service import TenantOrderService
    try:
        return await TenantOrderService(session).payment_eligibility(booking_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/create", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payment_in: PaymentCreate, session: AsyncSession = Depends(get_db_session), current_user: User = Depends(require_tenant), idempotency_key: str = Header(..., alias="Idempotency-Key")) -> Payment:
    try:
        return await PaymentOrderService(session).create(payment_in.booking_id, current_user.id, idempotency_key, current_user.username, payment_in.payment_method)
    except Exception as exc:
        _raise(exc)


@router.get("/methods/availability", response_model=list[PaymentMethodAvailability])
async def payment_method_availability() -> list:
    """只公布服务端实际可用方式；生产配置缺失时明确返回暂未开通。"""
    return provider_availability()


@router.post("/merchant-webhooks/{provider_name}", response_model=PaymentResponse)
async def merchant_webhook(
    provider_name: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    signature: str = Header(default="", alias="X-Payment-Signature"),
) -> Payment:
    """真实商户 webhook 统一入口；适配器联调验收前保持关闭。"""
    providers = {"wechat_pay": WeChatPayProvider, "alipay": AlipayProvider, "card_checkout": CardCheckoutProvider}
    provider_class = providers.get(provider_name)
    if not provider_class:
        raise HTTPException(404, "未知支付服务商")
    provider = provider_class()
    try:
        # 不记录原始回调正文；业务层只保存 SHA-256 摘要与已验证事件编号。
        return await PaymentOrderService(session, provider).process_webhook(await request.body(), signature)
    except ProviderUnavailableError:
        raise HTTPException(503, "该支付方式暂未开通")
    except Exception as exc:
        _raise(exc)


@router.get("/by-booking/{booking_id}", response_model=PaymentResponse)
async def get_by_booking(booking_id: int, session: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Payment:
    payment = await session.scalar(select(Payment).options(selectinload(Payment.booking)).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc()))
    if not payment: raise HTTPException(404, "支付订单不存在")
    if payment.user_id != current_user.id and current_user.role != UserRole.admin: raise HTTPException(403, "无权查看")
    return payment


@router.get("/result/by-booking/{booking_id}", response_model=PaymentResultResponse)
async def get_payment_result(booking_id: int, session: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> dict:
    """返回结果页摘要；租客不能通过修改 URL 查看他人订单。"""
    payment = await session.scalar(select(Payment).options(selectinload(Payment.booking)).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc()))
    if not payment: raise HTTPException(404, "支付订单不存在")
    if not _can_view_payment(payment, current_user): raise HTTPException(403, "无权查看该订单")
    booking = payment.booking
    image = await session.scalar(select(PropertyImage).where(PropertyImage.property_id == booking.property_id).order_by(PropertyImage.is_primary.desc(), PropertyImage.sort_order, PropertyImage.id))
    data = PaymentResponse.model_validate(payment).model_dump()
    data.update({
        "property_image_url": f"/api/v1/uploads/{image.filename}" if image else None,
        "booking_created_at": booking.created_at,
        "status_updated_at": booking.updated_at,
        "failure_reason": SAFE_FAILURE_MESSAGES.get(payment.order_status or ""),
    })
    return data


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, session: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Payment:
    payment = await session.scalar(select(Payment).options(selectinload(Payment.booking)).where(Payment.id == payment_id))
    if not payment: raise HTTPException(404, "支付订单不存在")
    if payment.user_id != current_user.id and current_user.role != UserRole.admin: raise HTTPException(403, "无权查看")
    return payment


@router.post("/webhooks/mock", response_model=PaymentResponse)
async def mock_webhook(request: Request, session: AsyncSession = Depends(get_db_session), signature: str = Header(..., alias="X-Mock-Signature")) -> Payment:
    try: return await PaymentOrderService(session).process_webhook(await request.body(), signature)
    except Exception as exc: _raise(exc)


@router.get("/mock-checkout/{checkout_id}", response_class=HTMLResponse)
async def mock_checkout(checkout_id: str, session: AsyncSession = Depends(get_db_session)) -> str:
    payment = await session.scalar(select(Payment).where(Payment.provider_checkout_id == checkout_id))
    if not payment: raise HTTPException(404, "测试收银台不存在")
    display_amount = Decimal(payment.settlement_amount_minor) / Decimal(100)
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>本地测试收银台</title><style>body{{font:16px system-ui;background:#f4f6f9;margin:0}}main{{max-width:520px;margin:10vh auto;background:white;padding:32px;border-radius:16px;box-shadow:0 8px 30px #0002}}button{{padding:13px 20px;margin:8px;border:0;border-radius:8px;cursor:pointer}}.ok{{background:#1769e0;color:white}}.warn{{color:#a33}}</style><main><h1>本地测试收银台</h1><p>不会采集银行卡号、有效期或 CVV，也不会产生真实扣款。</p><p>测试金额：<strong>{payment.settlement_currency} {display_amount:.2f}</strong></p><form method="post" action="/api/v1/payments/mock-checkout/{checkout_id}/complete"><button class="ok" name="outcome" value="succeeded">模拟支付成功</button><button name="outcome" value="failed">模拟支付失败</button></form><p class="warn">仅限本地开发测试模式</p></main></html>'''


@router.post("/mock-checkout/{checkout_id}/complete")
async def complete_mock_checkout(checkout_id: str, request: Request, session: AsyncSession = Depends(get_db_session)) -> RedirectResponse:
    payment = await session.scalar(select(Payment).where(Payment.provider_checkout_id == checkout_id))
    if not payment: raise HTTPException(404, "测试收银台不存在")
    form = parse_qs((await request.body()).decode()); outcome = "succeeded" if form.get("outcome", [""])[0] == "succeeded" else "failed"
    event = {"event_id": f"evt_{uuid.uuid4().hex}", "provider_payment_id": payment.provider_payment_id, "merchant_account": payment.provider_merchant_account, "order_number": payment.out_trade_no, "amount_minor": payment.settlement_amount_minor, "currency": payment.settlement_currency, "status": outcome, "transaction_id": f"mock_txn_{uuid.uuid4().hex}"}
    payload = json.dumps(event, separators=(",", ":"), sort_keys=True).encode(); provider = MockHostedPaymentProvider()
    result = await PaymentOrderService(session).process_webhook(payload, provider.sign(payload))
    page = "success" if result.status == PaymentStatus.success else "payment-status"
    return RedirectResponse(f"{get_settings().frontend_url}/booking/order/{payment.booking_id}/{page}", status_code=303)

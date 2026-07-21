"""Celery tasks for WeChat Pay operations.

Includes:
  - Polling pending payments for status sync
  - Sending payment confirmation template messages
  - Closing expired orders
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.payment import Payment, PaymentStatus
from app.services.payment_service import WeChatPayService

logger = logging.getLogger(__name__)

PAYMENT_SUCCESS_TEMPLATE = "payment_success_template_id"
PAYMENT_FAILED_TEMPLATE = "payment_failed_template_id"


async def _sync_single_payment(payment: Payment, session: AsyncSession) -> bool:
    """Sync a single payment's status from WeChat Pay.

    Returns True if the payment status changed to a final state.
    """
    if not payment.out_trade_no:
        return False

    wechat_pay = WeChatPayService()
    try:
        wx_order = await wechat_pay.query_by_out_trade_no(payment.out_trade_no)
    except Exception:
        logger.warning("Failed to query WeChat for payment %s", payment.id)
        return False

    trade_state = wx_order.get("trade_state", "")
    original_status = payment.status

    if trade_state == "SUCCESS":
        payment.status = PaymentStatus.success
        payment.transaction_id = wx_order.get("transaction_id")
        payment.trade_state = trade_state
        payment.trade_state_desc = wx_order.get("trade_state_desc")
        success_time = wx_order.get("success_time")
        if success_time:
            payment.paid_at = datetime.fromisoformat(success_time)
    elif trade_state in ("CLOSED", "PAYERROR", "REVOKED"):
        payment.status = PaymentStatus.failed
        payment.trade_state = trade_state
        payment.trade_state_desc = wx_order.get("trade_state_desc")

    if payment.status != original_status:
        # Update associated booking
        from app.models.booking import Booking
        booking = await session.get(Booking, payment.booking_id)
        if booking:
            if payment.status == PaymentStatus.success:
                booking.deposit_status = "confirmed"
            elif payment.status == PaymentStatus.failed:
                booking.deposit_status = "unpaid"

        await session.commit()

        # 邮件通知租客
        try:
            from app.tasks.notification_tasks import send_email_notification_with_template
            from app.core.config import get_settings
            settings = get_settings()
            amount_str = f"{payment.amount / 100:.2f}"
            if payment.status == PaymentStatus.success:
                send_email_notification_with_template.delay(
                    user_id=payment.user_id,
                    subject="支付到账",
                    template_name="payment_received",
                    context={
                        "user_name": "",  # Celery task 内查用户后填充，这里暂用空
                        "booking_id": str(payment.booking_id),
                        "amount": amount_str,
                        "payment_id": payment.id,
                        "paid_at": payment.paid_at.strftime("%Y-%m-%d %H:%M") if payment.paid_at else "",
                        "frontend_url": settings.frontend_url,
                    },
                )
            else:
                send_email_notification_with_template.delay(
                    user_id=payment.user_id,
                    subject="支付失败",
                    template_name="payment_failed",
                    context={
                        "user_name": "",
                        "booking_id": str(payment.booking_id),
                        "amount": amount_str,
                        "payment_id": payment.id,
                        "reason": payment.trade_state_desc or "未知错误",
                        "frontend_url": settings.frontend_url,
                    },
                )
        except Exception:
            pass

        logger.info(
            "Payment %s synced: %s -> %s",
            payment.id,
            original_status.value,
            payment.status.value,
        )
        return True

    return False


@celery_app.task(
    name="sync_pending_payments",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def sync_pending_payments() -> dict:
    """Periodic task: query WeChat Pay for all pending payments to sync status.

    Should be scheduled via Celery Beat, e.g., every 5 minutes.
    """

    async def _run() -> dict:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            stmt = select(Payment).where(
                Payment.status.in_([
                    PaymentStatus.pending,
                    PaymentStatus.processing,
                ])
            )
            result = await session.execute(stmt)
            payments = result.scalars().all()

            synced = 0
            for payment in payments:
                try:
                    if await _sync_single_payment(payment, session):
                        synced += 1
                except Exception:
                    logger.exception("Error syncing payment %s", payment.id)

            await engine.dispose()
            return {"total": len(payments), "synced": synced}

    return asyncio.run(_run())


@celery_app.task(
    name="close_expired_payments",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def close_expired_payments() -> dict:
    """Periodic task: close payments that have been pending for too long.

    WeChat Pay orders expire after a configurable period (default ~2h).
    This task closes them locally and on the WeChat side.
    """

    async def _run() -> dict:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

        async with async_session() as session:
            stmt = select(Payment).where(
                Payment.status == PaymentStatus.pending,
                Payment.created_at < cutoff,
            )
            result = await session.execute(stmt)
            payments = result.scalars().all()

            wechat_pay = WeChatPayService()
            closed = 0
            for payment in payments:
                try:
                    if payment.out_trade_no:
                        await wechat_pay.close_order(payment.out_trade_no)
                    payment.status = PaymentStatus.closed
                    payment.trade_state_desc = "Expired - closed by system"

                    from app.models.booking import Booking
                    booking = await session.get(Booking, payment.booking_id)
                    if booking and booking.deposit_status == "paying":
                        booking.deposit_status = "unpaid"

                    closed += 1
                    # 邮件通知租客支付已过期
                    try:
                        from app.tasks.notification_tasks import send_email_notification_with_template
                        from app.core.config import get_settings
                        settings = get_settings()
                        send_email_notification_with_template.delay(
                            user_id=payment.user_id,
                            subject="支付已过期",
                            template_name="payment_expired",
                            context={
                                "user_name": "",
                                "booking_id": str(payment.booking_id),
                                "amount": f"{payment.amount / 100:.2f}",
                                "payment_id": payment.id,
                                "frontend_url": settings.frontend_url,
                            },
                        )
                    except Exception:
                        pass
                except Exception:
                    logger.exception("Error closing payment %s", payment.id)

            if closed:
                await session.commit()

            await engine.dispose()
            return {"total": len(payments), "closed": closed}

    return asyncio.run(_run())


@celery_app.task(
    name="send_payment_result_message",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_payment_result_message(
    user_id: int,
    payment_id: str,
    status: str,
    amount: int,
    out_trade_no: str,
) -> None:
    """Send payment result template message to the user."""

    async def _run() -> None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            from app.models.user import User
            user = await session.get(User, user_id)
            if not user or not user.wechat_openid:
                logger.warning("User %s has no openid, skipping payment notification", user_id)
                await engine.dispose()
                return

            openid = user.wechat_openid
            await engine.dispose()

        from app.services.wechat_service import WeChatService
        wechat = WeChatService()

        if status == "success":
            template_id = PAYMENT_SUCCESS_TEMPLATE
            data = {
                "first": {"value": "支付成功！"},
                "keyword1": {"value": f"¥{amount / 100:.2f}"},
                "keyword2": {"value": out_trade_no},
                "keyword3": {"value": datetime.now().strftime("%Y-%m-%d %H:%M")},
                "remark": {"value": "您的预约押金已支付成功，房东将尽快确认。"},
            }
        else:
            template_id = PAYMENT_FAILED_TEMPLATE
            data = {
                "first": {"value": "支付未完成"},
                "keyword1": {"value": f"¥{amount / 100:.2f}"},
                "keyword2": {"value": out_trade_no},
                "keyword3": {"value": datetime.now().strftime("%Y-%m-%d %H:%M")},
                "remark": {"value": "支付未成功，请重新发起支付。"},
            }

        try:
            await wechat.send_template_message(
                openid=openid,
                template_id=template_id,
                data=data,
                page=f"pages/booking/detail",
            )
            logger.info("Payment result message sent to user %s", user_id)
        except Exception:
            logger.exception("Failed to send payment result message to user %s", user_id)

    asyncio.run(_run())

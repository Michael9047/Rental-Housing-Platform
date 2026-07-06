import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.user import User
from app.services.wechat_service import WeChatService
from app.services.sms_service import SmsService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

# Template IDs - replace with actual WeChat template IDs in production
BOOKING_CONFIRM_TEMPLATE = "booking_confirm_template_id"
BOOKING_REMINDER_TEMPLATE = "booking_reminder_template_id"
STATUS_UPDATE_TEMPLATE = "status_update_template_id"


def _build_booking_confirm_data(booking_info: dict) -> dict:
    """Build template message data for booking confirmation."""
    return {
        "first": {"value": "您的预约已确认！"},
        "keyword1": {"value": booking_info.get("property_title", "")},
        "keyword2": {"value": booking_info.get("booking_time", "")},
        "keyword3": {"value": booking_info.get("landlord_phone", "")},
        "remark": {"value": booking_info.get("remark", "请按时前往看房。")},
    }


def _build_booking_reminder_data(booking_info: dict) -> dict:
    """Build template message data for booking reminder."""
    return {
        "first": {"value": "看房提醒"},
        "keyword1": {"value": booking_info.get("property_title", "")},
        "keyword2": {"value": booking_info.get("booking_time", "")},
        "keyword3": {"value": booking_info.get("address", "")},
        "remark": {"value": "您的预约看房时间即将到来，请做好准备。"},
    }


def _build_status_update_data(notification_info: dict) -> dict:
    """Build template message data for status update notifications."""
    return {
        "first": {"value": notification_info.get("title", "状态更新通知")},
        "keyword1": {"value": notification_info.get("content", "")},
        "keyword2": {"value": notification_info.get("updated_at", "")},
        "remark": {"value": "点击查看详情。"},
    }


@celery_app.task(
    name="send_wechat_template_message",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_wechat_template_message(
    user_id: int,
    template_id: str,
    data: dict,
    page: str | None = None,
) -> dict:
    """Send a WeChat template message to a user asynchronously."""
    import asyncio

    async def _run() -> dict:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user or not user.wechat_openid:
                logger.warning("User %s has no wechat_openid, skipping template message", user_id)
                await engine.dispose()
                return {"status": "skipped", "reason": "no openid"}

            openid = user.wechat_openid
            await engine.dispose()

        wechat = WeChatService()
        try:
            result = await wechat.send_template_message(
                openid=openid,
                template_id=template_id,
                data=data,
                page=page,
            )
            logger.info("Template message sent to user %s: %s", user_id, result)
            return {"status": "sent", "msgid": result.get("msgid")}
        except Exception as exc:
            logger.exception("Failed to send template message to user %s", user_id)
            raise

    return asyncio.run(_run())


@celery_app.task(
    name="send_booking_confirm_message",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_booking_confirm_message(user_id: int, booking_info: dict) -> None:
    """Send booking confirmation template message."""
    data = _build_booking_confirm_data(booking_info)
    send_wechat_template_message.delay(
        user_id=user_id,
        template_id=BOOKING_CONFIRM_TEMPLATE,
        data=data,
        page=f"pages/booking/detail",
    )


@celery_app.task(
    name="send_booking_reminder_message",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_booking_reminder_message(user_id: int, booking_info: dict) -> None:
    """Send booking reminder template message."""
    data = _build_booking_reminder_data(booking_info)
    send_wechat_template_message.delay(
        user_id=user_id,
        template_id=BOOKING_REMINDER_TEMPLATE,
        data=data,
        page=f"pages/booking/detail",
    )


# ── SMS Notification Task ──────────────────────────────────────────

@celery_app.task(
    name="send_sms_notification",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_sms_notification(user_id: int, content: str) -> dict:
    """Send an SMS notification to a user."""
    import asyncio

    async def _run() -> dict:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user or not user.phone:
                logger.warning("User %s has no phone, skipping SMS", user_id)
                await engine.dispose()
                return {"status": "skipped", "reason": "no phone"}

            phone = user.phone
            await engine.dispose()

        sms = SmsService()
        try:
            # 号码认证模板 100001: "您的验证码为${code}。${min}分钟内有效"
            import uuid
            code = content[:20] if content else str(uuid.uuid4().hex[:6])
            result = await sms.send(
                phone_number=phone,
                template_param={"code": code, "min": "5"},
            )
            logger.info("SMS sent to user %s: %s", user_id, result)
            return result
        except Exception as exc:
            logger.exception("Failed to send SMS to user %s", user_id)
            raise

    return asyncio.run(_run())


# ── Email Notification Task ─────────────────────────────────────────

@celery_app.task(
    name="send_email_notification",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_email_notification(user_id: int, subject: str, html_body: str) -> dict:
    """Send an email notification to a user."""
    import asyncio

    async def _run() -> dict:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user or not user.email:
                logger.warning("User %s has no email, skipping email", user_id)
                await engine.dispose()
                return {"status": "skipped", "reason": "no email"}

            to_email = user.email
            await engine.dispose()

        email_svc = EmailService()
        try:
            result = await email_svc.send(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
            )
            logger.info("Email sent to user %s: %s", user_id, result)
            return result
        except Exception as exc:
            logger.exception("Failed to send email to user %s", user_id)
            raise

    return asyncio.run(_run())

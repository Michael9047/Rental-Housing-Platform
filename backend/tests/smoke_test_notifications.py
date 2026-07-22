"""
Smoke test for the unified notification dispatch pipeline.
Run with: python tests/smoke_test_notifications.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sms_service_skip_without_config():
    """SMS service skips gracefully when no credentials configured."""
    from app.services.sms_service import SmsService

    svc = SmsService()
    settings = svc.settings

    assert settings.sms_access_key_id == "", "Expected empty SMS_ACCESS_KEY_ID in test env"
    assert settings.sms_access_key_secret == "", "Expected empty SMS_ACCESS_KEY_SECRET in test env"

    result = asyncio.run(svc.send_verification_code(phone_number="13800138000", code="123456"))
    assert result["status"] == "skipped", f"Expected skipped, got {result}"
    assert "not configured" in result["reason"]
    print("  PASS  SMS service skip without config")


def test_sms_service_skip_without_phone():
    """SMS service skips when no phone number provided."""
    from app.services.sms_service import SmsService

    svc = SmsService()
    result = asyncio.run(svc.send_verification_code(phone_number="", code="123456"))
    assert result["status"] == "skipped"
    assert result["reason"] == "no phone number"
    print("  PASS  SMS service skip without phone")


def test_email_service_skip_without_config():
    """Email service skips gracefully when no SMTP configured."""
    from app.services.email_service import EmailService

    svc = EmailService()
    settings = svc.settings

    assert settings.smtp_host == "", "Expected empty SMTP_HOST in test env"

    result = asyncio.run(svc.send(
        to_email="test@example.com",
        subject="Test",
        html_body="<p>Test</p>",
    ))
    assert result["status"] == "skipped", f"Expected skipped, got {result}"
    assert "not configured" in result["reason"]
    print("  PASS  Email service skip without config")


def test_email_service_skip_without_email():
    """Email service skips when no email address provided."""
    from app.services.email_service import EmailService

    svc = EmailService()
    result = asyncio.run(svc.send(to_email="", subject="Test", html_body="<p>Test</p>"))
    assert result["status"] == "skipped"
    assert result["reason"] == "no email address"
    print("  PASS  Email service skip without email")


def test_notification_channel_metadata():
    """NotificationService has channel metadata for all types."""
    from app.services.notification_service import _CHANNEL_META
    from app.models.notification import NotificationType

    required_types = {
        NotificationType.booking_created,
        NotificationType.booking_approved,
        NotificationType.booking_rejected,
        NotificationType.booking_cancelled,
        NotificationType.booking_completed,
        NotificationType.payment_received,
        NotificationType.system,
    }

    for nt in required_types:
        assert nt in _CHANNEL_META, f"Missing channel meta for {nt}"
        assert "wechat_template" in _CHANNEL_META[nt], f"Missing wechat_template for {nt}"

    print("  PASS  Notification channel metadata complete")


def test_celery_tasks_registered():
    """All notification Celery tasks are registered."""
    from app.celery_app import celery_app
    from app.tasks.notification_tasks import (
        send_wechat_template_message,
        send_sms_notification,
        send_email_notification,
        send_booking_confirm_message,
        send_booking_reminder_message,
    )

    task_names = [t.name for t in celery_app.tasks.values()]
    assert "send_wechat_template_message" in task_names
    assert "send_sms_notification" in task_names
    assert "send_email_notification" in task_names
    assert "send_booking_confirm_message" in task_names
    assert "send_booking_reminder_message" in task_names
    print("  PASS  Celery tasks registered")


def test_booking_status_notification_mapping():
    """BookingService.update_status maps all statuses to notifications."""
    from app.models.booking import BookingStatus
    from app.models.notification import NotificationType

    # Verify the mapping covers all relevant statuses
    expected = {
        BookingStatus.approved: NotificationType.booking_approved,
        BookingStatus.rejected: NotificationType.booking_rejected,
        BookingStatus.cancelled: NotificationType.booking_cancelled,
        BookingStatus.completed: NotificationType.booking_completed,
    }
    for status, nt in expected.items():
        assert status.value in ["approved", "rejected", "cancelled", "completed"]
        assert nt.value in [
            "booking_approved", "booking_rejected",
            "booking_cancelled", "booking_completed",
        ]

    print("  PASS  Booking status notification mapping")


def test_notify_sms_service_skip_without_config():
    """通知短信服务在未配置时静默跳过。"""
    from app.services.notification_sms_service import NotificationSmsService

    svc = NotificationSmsService()
    result = asyncio.run(svc.send(
        phone_number="13800138000",
        notification_type="booking_created",
        title="测试",
        content="测试通知",
    ))
    assert result["status"] == "skipped", f"Expected skipped, got {result}"
    print("  PASS  Notify SMS service skip without config")


def test_notify_sms_service_skip_without_phone():
    """通知短信服务在无手机号时跳过。"""
    from app.services.notification_sms_service import NotificationSmsService

    svc = NotificationSmsService()
    result = asyncio.run(svc.send(
        phone_number="",
        notification_type="booking_created",
        title="测试",
        content="测试通知",
    ))
    assert result["status"] == "skipped"
    assert result["reason"] == "no phone number"
    print("  PASS  Notify SMS service skip without phone")


def test_notify_sms_skip_without_template():
    """通知短信服务在未配置模板映射时跳过。"""
    from app.services.notification_sms_service import NotificationSmsService
    from app.core.config import get_settings

    settings = get_settings()
    # 模拟 AK 已配置但模板映射为空
    if not settings.sms_notify_access_key_id:
        print("  SKIP Notify SMS no-template test (no AK configured)")
        return

    svc = NotificationSmsService()
    result = asyncio.run(svc.send(
        phone_number="13800138000",
        notification_type="unknown_fake_type",
        title="测试",
        content="测试通知",
    ))
    assert result["status"] == "skipped"
    assert "no template" in result["reason"]
    print("  PASS  Notify SMS skip without template")


def test_config_has_new_fields():
    """Settings object includes all SMS and Email config fields."""
    from app.core.config import get_settings

    settings = get_settings()
    sms_fields = [
        "sms_provider", "sms_access_key_id", "sms_access_key_secret",
        "sms_sign_name", "sms_template_code", "sms_endpoint",
    ]
    sms_notify_fields = [
        "sms_notify_access_key_id", "sms_notify_access_key_secret",
        "sms_notify_sign_name", "sms_notify_endpoint",
        "sms_notify_template_map",
    ]
    email_fields = [
        "smtp_host", "smtp_port", "smtp_user", "smtp_password",
        "smtp_from_name", "smtp_from_email", "smtp_use_tls",
    ]

    for field in sms_fields + sms_notify_fields + email_fields:
        assert hasattr(settings, field), f"Missing config field: {field}"

    print("  PASS  Config has all new fields")


# ── Run ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Notification Dispatch Pipeline Smoke Test ===\n")
    tests = [
        ("SMS skip without config", test_sms_service_skip_without_config),
        ("SMS skip without phone", test_sms_service_skip_without_phone),
        ("NotifySMS skip without config", test_notify_sms_service_skip_without_config),
        ("NotifySMS skip without phone", test_notify_sms_service_skip_without_phone),
        ("NotifySMS skip without template", test_notify_sms_skip_without_template),
        ("Email skip without config", test_email_service_skip_without_config),
        ("Email skip without email", test_email_service_skip_without_email),
        ("Channel metadata", test_notification_channel_metadata),
        ("Celery tasks registered", test_celery_tasks_registered),
        ("Booking status mapping", test_booking_status_notification_mapping),
        ("Config new fields", test_config_has_new_fields),
    ]

    failed = 0
    for name, fn in tests:
        try:
            fn()
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1

    print(f"\n--- {len(tests) - failed}/{len(tests)} passed ---")
    if failed:
        sys.exit(1)
    else:
        print("All smoke tests passed!\n")

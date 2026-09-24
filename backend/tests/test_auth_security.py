"""认证安全工具与敏感日志防护测试。"""

from app.core.security import mask_phone


def test_mask_phone_hides_middle_digits() -> None:
    assert mask_phone("13800138000") == "138****8000"
    assert mask_phone("+447700900123") == "+44****0123"


def test_mask_phone_hides_short_values() -> None:
    assert mask_phone("1234567") == "***"
